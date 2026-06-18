#!/usr/bin/env python3
"""RESUMABLE full-corpus seed-free scorer — the restart-survivable "finish it" driver.

Scores every registered clip (cv_eval.CLIPS) plus any 4K proxies, on the shipped seed-free
AUTO path (tracker="auto", no seed/rim/angle oracle), and APPENDS each result to the durable
`dataset/cv_seedfree_scores.csv` the instant it's computed. On restart it skips set_ids already
in the CSV, so a wiped container resumes instead of restarting — the antidote to the multi-hour
re-score trap (learnings #29/#30).

    python dataset/tools/score_corpus.py            # all registered clips not yet scored
    python dataset/tools/score_corpus.py --only 20260529-DL-1 ...
    python dataset/tools/score_corpus.py --rescore  # ignore the CSV, re-score everything
"""
from __future__ import annotations
import csv, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
REPO = os.path.dirname(DATASET)
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(REPO, "analysis", "scripts"))
import cv_eval  # noqa: E402
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402

CSV_PATH = os.path.join(DATASET, "cv_seedfree_scores.csv")
COLS = ["set_id", "seed_free_count", "source"]
SRC = os.environ.get("SCORE_SOURCE", "2026-06-18 corpus re-score")


def load_scored():
    out = {}
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            out[r["set_id"]] = r
    return out


def write_all(rows):
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader()
        for sid in sorted(rows):
            w.writerow({c: rows[sid].get(c, "") for c in COLS})


def resolve_target(sid):
    """Return a flow-able path: a cached 4K proxy if one exists, else the registered clip."""
    proxy = os.path.join(DATASET, "raw", f"{sid}_proxy.mp4")
    if os.path.exists(proxy):
        return proxy
    rel = cv_eval.CLIPS[sid][0]
    return resolve_clip(rel, REPO)


def main():
    args = sys.argv[1:]
    rescore = "--rescore" in args
    args = [a for a in args if a != "--rescore"]
    only = args[1:] if args[:1] == ["--only"] else None

    targets = only or list(cv_eval.CLIPS)
    rows = load_scored()
    print(f"corpus scorer: {len(targets)} targets, {len(rows)} already in CSV, src='{SRC}'", flush=True)
    for sid in targets:
        if sid not in cv_eval.CLIPS:
            print(f"  {sid:<18} [not in CLIPS — skip]", flush=True); continue
        if not rescore and sid in rows:
            print(f"  {sid:<18} = {rows[sid]['seed_free_count']:>2}  [cached, skip]", flush=True); continue
        t0 = time.time()
        try:
            clip = resolve_target(sid)
            reps, meta = VideoVelocitySource(VideoConfig(tracker="auto")).estimate(clip)
            n = len(reps)
        except Exception as e:
            print(f"  {sid:<18} ERR {type(e).__name__}: {e}", flush=True); continue
        refn, _, _, _ = cv_eval.gt_counts(sid)
        gt = cv_eval._true_gt(sid, refn)
        rows[sid] = {"set_id": sid, "seed_free_count": n, "source": SRC}
        write_all(rows)          # persist AFTER EACH clip — restart-survivable
        d = f"{n-gt:+d}" if gt is not None else "?"
        print(f"  {sid:<18} = {n:>2} (GT {gt} {d})  honest={meta.get('track_honest','?')} "
              f"[{time.time()-t0:.0f}s]", flush=True)
    print("done.", flush=True)


if __name__ == "__main__":
    main()
