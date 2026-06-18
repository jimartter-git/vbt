#!/usr/bin/env python3
"""Corpus COVERAGE check — the guardrail against the "only analyzed a subset" blind spot.

The eval boards (`cv_eval.CLIPS`, the watch `SESSIONS` dicts) are hand-maintained registries.
Anything uploaded to R2 / git that isn't manually added is silently skipped — which is exactly
how the 06-13 deadlifts, 06-17 squats/RDLs, and 06-15 ROW-3/5 went un-analyzed by CV for a while.

This reconciles the boards against the ACTUAL corpus and FAILS (exit 1) if anything with data
is not wired into its eval:
  * VIDEO source of truth = `dataset/raw/manifest.csv` (R2 masters) ∪ local `dataset/raw/*.mov|mp4`.
  * WATCH source of truth = `dataset/raw/*_watch.csv`.
  * GROUND TRUTH = per-rep rows in `dataset/rep_metrics.csv` (Vitruve / SmartBarbell / watch_imu).
  * CV board = `cv_eval.CLIPS`; watch board = `wave_eval.SESSIONS`.

Run it at the START of any CV or watch work, and after every upload. The rule (CLAUDE.md):
when working CV, score ALL videos with GT; when working watch, use ALL watch sessions.

    python analysis/scripts/coverage.py
"""
from __future__ import annotations
import csv
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import cv_eval                      # noqa: E402  (CLIPS = the CV board)
from wave_eval import SESSIONS as WATCH_BOARD  # noqa: E402

REPO = cv_eval.REPO
RAW = os.path.join(REPO, "dataset", "raw")


def gt_vendors():
    """set_id -> set of vendors with per-rep ground-truth rows."""
    out = {}
    for r in csv.DictReader(open(os.path.join(REPO, "dataset", "rep_metrics.csv"))):
        if (r.get("rep_index") or "").strip():
            out.setdefault(r["set_id"], set()).add(r["vendor"])
    return out


def manifest_clips():
    """set_id -> (resolution, note) for every R2 master in the manifest."""
    out = {}
    p = os.path.join(RAW, "manifest.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            out[r["set_id"]] = (r.get("resolution", "?"), r.get("note", "")[:40])
    return out


def manifest_keys():
    p = os.path.join(RAW, "manifest.csv")
    return ({r.get("key") or r["filename"] for r in csv.DictReader(open(p))}
            | {r["filename"] for r in csv.DictReader(open(p))}) if os.path.exists(p) else set()


def r2_bucket_keys():
    """LIVE listing of the R2 bucket — the only way to catch a video UPLOADED but not yet
    in the manifest (the registry-vs-reality trap one level down). Returns set of keys or
    None if boto3/credentials are unavailable."""
    try:
        import boto3
        ak, sk = os.environ.get("R2_ACCESS_KEY_ID"), os.environ.get("R2_SECRET_ACCESS_KEY")
        if not (ak and sk):
            return None
        ep = os.environ.get("R2_ENDPOINT",
                            "https://6747d02e809e8e72687bb909e5cf302a.r2.cloudflarestorage.com")
        bucket = os.environ.get("R2_BUCKET", "vbt-video")
        s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk)
        keys, tok = set(), None
        while True:
            kw = {"Bucket": bucket, "MaxKeys": 1000}
            if tok:
                kw["ContinuationToken"] = tok
            r = s3.list_objects_v2(**kw)
            keys |= {o["Key"] for o in r.get("Contents", [])}
            if r.get("IsTruncated"):
                tok = r.get("NextContinuationToken")
            else:
                break
        return keys
    except Exception:
        return None


def main():
    gt = gt_vendors()
    manifest = manifest_clips()
    cv_board = set(cv_eval.CLIPS)
    watch_board = set(WATCH_BOARD)
    watch_csvs = {os.path.basename(p).replace("_watch.csv", "")
                  for p in glob.glob(os.path.join(RAW, "*_watch.csv"))}
    # every set_id that HAS a video (R2 manifest or a local CLIPS-referenced file)
    local_video = {sid for sid, v in cv_eval.CLIPS.items()
                   if os.path.exists(os.path.join(REPO, v[0]))}
    video_sids = set(manifest) | local_video

    gaps = 0

    print("=== CV coverage — videos with ground truth NOT in the scoring board ===")
    cv_gap = sorted(s for s in video_sids if s in gt and s not in cv_board)
    if cv_gap:
        gaps += len(cv_gap)
        for s in cv_gap:
            res = manifest.get(s, ("local", ""))[0]
            hint = "  (4K — needs proxy transcode)" if res.startswith(("3840", "2160")) else ""
            print(f"  ⚠ {s:<18} GT={sorted(gt[s])}  {res}{hint}")
    else:
        print("  ✓ every video with GT is in the CV board")

    print("\n=== WATCH coverage — watch CSVs NOT in the watch eval board ===")
    w_gap = sorted(watch_csvs - watch_board)
    if w_gap:
        gaps += len(w_gap)
        for s in w_gap:
            print(f"  ⚠ {s:<18} GT={sorted(gt.get(s, []))}")
    else:
        print("  ✓ every watch session is in the watch board")

    print("\n=== R2 bucket vs manifest — UPLOADED but not registered ===")
    r2 = r2_bucket_keys()
    if r2 is None:
        print("  (skipped — boto3 / R2 creds unavailable)")
    else:
        man_keys = manifest_keys()
        unreg = sorted(k for k in r2 if k not in man_keys)
        if unreg:
            gaps += len(unreg)
            for k in unreg:
                print(f"  ⚠ {k}  — in R2 but NOT in manifest.csv (add a row + register in the board)")
        else:
            print(f"  ✓ all {len(r2)} R2 objects are in the manifest")

    print("\n=== GT without any video OR watch capture (data filed, no signal source) ===")
    orphan = sorted(s for s in gt if s not in video_sids and s not in watch_csvs)
    for s in orphan:
        print(f"  · {s:<18} GT={sorted(gt[s])}  (set-level only? screenshot pending upload?)")
    if not orphan:
        print("  ✓ none")

    print(f"\nSUMMARY: CV board {len(cv_board)} clips · watch board {len(watch_board)} · "
          f"{len(video_sids)} videos · {len(watch_csvs)} watch sessions · {len(gt)} GT sets")
    if gaps:
        print(f"\n✗ {gaps} coverage GAP(S) — wire these into the boards before reporting any "
              f"aggregate (CLAUDE.md: use ALL videos for CV, ALL watch for watch).")
        return 1
    print("\n✓ no coverage gaps — the boards cover the full corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
