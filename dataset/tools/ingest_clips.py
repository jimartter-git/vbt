#!/usr/bin/env python3
"""Ingest CV-corpus video clips into the metadata store.

R2 holds the bytes; git holds the queryable metadata. This writes/updates:
  - dataset/raw/manifest.csv : storage/technical facts (sha/bytes/res/fps/codec/duration)
  - dataset/clips.csv        : a DRAFT human-annotation row, CV-prefilled with a
                               provisional rep count + a rough velocity-regime hint.
You then correct the subjective columns (angle/clutter/...) in a spreadsheet and
run build_db.py. Upserts by filename, so re-running enriches existing rows
(human annotations are preserved; only the CV draft + technical fields update).

Technical metadata comes from PyAV (a CV dep) or ffprobe, whichever is present.
The CV prefill runs our shipped seed-free AUTO estimator (no tap, no gym hint).

Usage:
  # local clips on disk:
  python dataset/tools/ingest_clips.py ~/Desktop/vbt --gym MaxFit
  # already-uploaded clips: pull each from R2 and enrich its manifest/clips row
  # (needs R2 read creds in the env: R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY)
  python dataset/tools/ingest_clips.py --from-manifest
  python dataset/tools/ingest_clips.py --from-manifest --only 20260613-DL-5.mov --sha
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


def _load(path, key):
    """Read a CSV into an ordered {key_value: row} dict (empty if absent)."""
    out = {}
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                k = (r.get(key) or "").strip()
                if k:
                    out[k] = r
    return out


def _write(path, cols, rows_by_key):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for k in sorted(rows_by_key):
            w.writerow({c: rows_by_key[k].get(c, "") for c in cols})


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


def _enrich(local_path, fn, man, clips, do_cv, do_sha):
    """Probe + (optional) CV-prefill one clip, upserting manifest + clips rows.
    Preserves existing human annotations; only fills technical + CV-draft fields."""
    sid = infer_set_id(fn)
    info = probe(local_path)
    m = man.setdefault(fn, dict.fromkeys(MANIFEST_COLS, ""))
    m.update(filename=fn, key=(m.get("key") or fn), bytes=os.path.getsize(local_path), **info)
    if not m.get("set_id"):
        m["set_id"] = sid
    if do_sha:
        m["sha256"] = sha256(local_path)

    c = clips.setdefault(fn, dict.fromkeys(CLIPS_COLS, ""))
    if not c.get("clip"):
        c.update(clip=fn, set_id=sid)
    if do_cv:
        try:
            d = cv_prefill(local_path)
            c["reps_cv"] = d["reps_cv"]; c["mean_vel_cv"] = d["mean_vel_cv"]
            c["cv_conf"] = d["cv_conf"]; c["cv_flags"] = d["cv_flags"]
            if not (c.get("velocity_regime") or "").strip():   # don't clobber a human label
                c["velocity_regime"] = d["velocity_regime"]
            print(f"  cv {fn}: {d['reps_cv']} reps (conf {d['cv_conf']})")
        except Exception as e:                                 # noqa: BLE001 — record, never abort
            c["cv_flags"] = f"cv_error:{type(e).__name__}"
            print(f"  cv FAILED {fn}: {e}")
    print(f"+ {fn}  {info['resolution']} {info['fps']}fps {info['codec']} "
          f"{m['bytes'] // (1 << 20) if str(m['bytes']).isdigit() else '?'}MB")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="clip files and/or directories (local mode)")
    ap.add_argument("--from-manifest", action="store_true",
                    help="enrich clips already listed in manifest.csv by pulling them from R2 "
                         "(resolve_clip); needs R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY in env")
    ap.add_argument("--only", default="", help="with --from-manifest: limit to one filename")
    ap.add_argument("--no-cv", action="store_true", help="skip the CV rep-count prefill")
    ap.add_argument("--sha", action="store_true", help="compute sha256 (slow on big files)")
    ap.add_argument("--gym", default="", help="prefill the gym column for new clips")
    ap.add_argument("--lift", default="", help="prefill the lift column for new clips")
    ap.add_argument("--force", action="store_true",
                    help="re-probe/re-CV even if the row already has data")
    args = ap.parse_args()

    man = _load(MANIFEST, "filename")
    clips = _load(CLIPS, "clip")
    do_cv = not args.no_cv

    if args.from_manifest:
        from vbt_video.clip_store import resolve_clip
        targets = [args.only] if args.only else list(man)
        for fn in targets:
            if fn not in man:
                print(f"not in manifest: {fn}"); continue
            row = clips.get(fn, {})
            done = (str(row.get("reps_cv") or "").strip()
                    and (man[fn].get("codec") or "").strip())
            if done and not args.force:
                print(f"skip (already enriched): {fn}"); continue
            try:
                local = resolve_clip(os.path.join("dataset", "raw", fn), REPO)
            except Exception as e:                              # noqa: BLE001
                print(f"resolve FAILED {fn}: {e}"); continue
            _enrich(local, fn, man, clips, do_cv, args.sha)
    else:
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
            print("no video files found (give paths, or use --from-manifest)"); return
        for path in files:
            fn = os.path.basename(path)
            if fn in man and not args.force:
                print(f"skip (already in manifest): {fn}"); continue
            _enrich(path, fn, man, clips, do_cv, args.sha)
            if args.gym:
                clips[fn]["gym"] = args.gym
            if args.lift and not clips[fn].get("lift"):
                clips[fn]["lift"] = args.lift

    _write(MANIFEST, MANIFEST_COLS, man)
    _write(CLIPS, CLIPS_COLS, clips)
    print(f"\nmanifest: {len(man)} clips | clips.csv: {len(clips)} rows")
    print("Next: review dataset/clips.csv, then python dataset/tools/build_db.py")


if __name__ == "__main__":
    main()
