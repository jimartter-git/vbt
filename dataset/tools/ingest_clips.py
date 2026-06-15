#!/usr/bin/env python3
"""Ingest CV-corpus video clips into the metadata store.

R2 holds the bytes; git holds the queryable metadata. For each clip this writes:
  - dataset/raw/manifest.csv : storage/technical facts (sha/bytes/res/fps/codec/duration)
  - dataset/clips.csv        : a DRAFT human-annotation row, CV-prefilled with a
                               provisional rep count + a rough velocity-regime hint.
You then correct the subjective columns (angle/clutter/...) in a spreadsheet and
run build_db.py. Idempotent: clips already in manifest.csv are skipped.

Technical metadata comes from PyAV (a CV dep) or ffprobe, whichever is present.
The CV prefill runs our shipped seed-free AUTO estimator (no tap, no gym hint).

Usage:
  python dataset/tools/ingest_clips.py ~/Desktop/vbt                 # a folder
  python dataset/tools/ingest_clips.py a.mov b.mov --gym Equinox     # explicit files
  python dataset/tools/ingest_clips.py <dir> --no-cv --sha           # fast / with checksum
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
REPO = os.path.dirname(DATASET)
MANIFEST = os.path.join(DATASET, "raw", "manifest.csv")
CLIPS = os.path.join(DATASET, "clips.csv")
sys.path.insert(0, os.path.join(REPO, "analysis"))

VIDEO_EXT = (".mov", ".mp4", ".m4v")
MANIFEST_COLS = ["filename", "set_id", "sha256", "bytes", "resolution", "fps",
                 "codec", "duration_s", "url", "key", "note"]
CLIPS_COLS = ["clip", "lift", "load_kg", "load_unit", "gym", "equipment", "angle_kind",
              "angle_quality", "background_clutter", "occlusion", "lighting",
              "velocity_regime", "tempo_notes", "reps_cv", "reps_true", "mean_vel_cv",
              "cv_conf", "cv_flags", "has_gt", "set_id", "notes"]


def _existing(path, key):
    if not os.path.exists(path):
        return set()
    with open(path, newline="") as f:
        return {r[key].strip() for r in csv.DictReader(f) if r.get(key, "").strip()}


def _probe_av(path):
    try:
        import av
    except Exception:
        return None
    try:
        with av.open(path) as c:
            v = next(s for s in c.streams if s.type == "video")
            w, h = v.codec_context.width, v.codec_context.height
            fps = round(float(v.average_rate), 2) if v.average_rate else ""
            dur = round(float(c.duration) / 1e6, 1) if c.duration else ""
            return dict(resolution=f"{w}x{h}", fps=fps, codec=v.codec_context.name, duration_s=dur)
    except Exception:
        return None


def _probe_ffprobe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
             "-show_format", path], capture_output=True, text=True, check=True).stdout
        j = json.loads(out)
        v = next(s for s in j.get("streams", []) if s.get("codec_type") == "video")
        num, den = (v.get("avg_frame_rate", "0/1").split("/") + ["1"])[:2]
        fps = round(float(num) / float(den), 2) if float(den) else ""
        dur = round(float(j.get("format", {}).get("duration", 0)), 1) or ""
        return dict(resolution=f"{v.get('width')}x{v.get('height')}", fps=fps,
                    codec=v.get("codec_name", ""), duration_s=dur)
    except Exception:
        return None


def probe(path):
    return (_probe_av(path) or _probe_ffprobe(path)
            or dict(resolution="", fps="", codec="", duration_s=""))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def infer_set_id(fn):
    m = re.match(r"(\d{8}[a-z]?-[A-Za-z]{2,3}-\d+)", os.path.splitext(fn)[0])
    return m.group(1) if m else ""


def cv_prefill(path):
    """Run the shipped seed-free AUTO estimator; return DRAFT fields to verify."""
    from vbt_video import VideoConfig, VideoVelocitySource
    cfg = VideoConfig(tracker="auto", rep_gate="relative")
    reps, meta = VideoVelocitySource(cfg).estimate(path, seed_bbox=None)
    mv = [r["mean_velocity"] for r in reps]
    n = len(reps)
    flags = []
    if meta.get("scale_suspect"):
        flags.append("scale_suspect")
    if meta.get("static_track_suspect"):
        flags.append("static_seed")
    regime = ""                       # rough hint only — VERIFY (load-blind, no per-rep timing)
    if n >= 3 and mv and max(mv) > 0:
        loss = (max(mv) - sum(sorted(mv)[:2]) / 2) / max(mv)
        if max(mv) > 0.7 and loss < 0.10:
            regime = "speed_work?"
        elif loss > 0.15:
            regime = "normal?"
    return dict(reps_cv=n, mean_vel_cv=(round(sum(mv) / len(mv), 3) if mv else ""),
                cv_conf=round(meta.get("track_confidence", 0), 2),
                cv_flags="|".join(flags), velocity_regime=regime)


def _append(path, cols, rows):
    if not rows:
        return
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(cols)
    with open(path) as f:
        tail = f.read()
    with open(path, "a", newline="") as f:
        if tail and not tail.endswith("\n"):
            f.write("\n")
        w = csv.DictWriter(f, fieldnames=cols)
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="clip files and/or directories")
    ap.add_argument("--no-cv", action="store_true", help="skip the CV rep-count prefill")
    ap.add_argument("--sha", action="store_true", help="compute sha256 (slow on big files)")
    ap.add_argument("--gym", default="", help="prefill the gym column for this batch")
    ap.add_argument("--lift", default="", help="prefill the lift column for this batch")
    ap.add_argument("--force", action="store_true", help="re-probe clips already in manifest")
    args = ap.parse_args()

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for ext in VIDEO_EXT:
                files += glob.glob(os.path.join(p, f"*{ext}"))
                files += glob.glob(os.path.join(p, f"*{ext.upper()}"))
        elif os.path.isfile(p):
            files.append(p)
    files = sorted(set(files))
    if not files:
        print("no video files found")
        return

    have = set() if args.force else _existing(MANIFEST, "filename")
    man_new, clip_new = [], []
    for path in files:
        fn = os.path.basename(path)
        if fn in have:
            print(f"skip (already in manifest): {fn}")
            continue
        info = probe(path)
        sid = infer_set_id(fn)
        man_new.append(dict(filename=fn, set_id=sid,
                            sha256=(sha256(path) if args.sha else ""),
                            bytes=os.path.getsize(path), url="", key=fn, note="", **info))
        draft = dict.fromkeys(CLIPS_COLS, "")
        draft.update(clip=fn, gym=args.gym, lift=args.lift, set_id=sid)
        if not args.no_cv:
            try:
                draft.update(cv_prefill(path))
                print(f"  cv {fn}: {draft['reps_cv']} reps (conf {draft['cv_conf']})")
            except Exception as e:                       # noqa: BLE001 — record, never abort the batch
                draft["cv_flags"] = f"cv_error:{type(e).__name__}"
                print(f"  cv FAILED {fn}: {e}")
        clip_new.append(draft)
        print(f"+ {fn}  {info['resolution']} {info['fps']}fps {info['codec']} "
              f"{man_new[-1]['bytes'] // (1 << 20)}MB")

    _append(MANIFEST, MANIFEST_COLS, man_new)
    _append(CLIPS, CLIPS_COLS, clip_new)
    print(f"\nmanifest += {len(man_new)} | clips += {len(clip_new)}")
    if clip_new:
        print("Next: edit dataset/clips.csv (angle/clutter/regime/load...), "
              "then python dataset/tools/build_db.py")


if __name__ == "__main__":
    main()
