#!/usr/bin/env python3
"""Verify ONE clip with a candidate flow tap seed, mirroring vel_eval --tap config.

Usage:
  python3 _verify_oneclip.py SET_ID CLIPPATH x y w h [t] [rim_px rim_t]

Runs the flow tracker with the human-grade config (gate + transit_aware + rim).
Prints reps, set-MV, conf, yspan so we can confirm count==GT before registering.
Run as an isolated subprocess; set cv2 to single thread.
"""
import sys, os
import cv2
cv2.setNumThreads(1)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402
import numpy as np  # noqa: E402


def main():
    a = sys.argv
    sid = a[1]
    clippath = a[2]
    x, y, w, h = int(a[3]), int(a[4]), int(a[5]), int(a[6])
    seed = (x, y, w, h)
    seed_time = float(a[7]) if len(a) > 7 and a[7] != "-" else None
    rim_px = int(a[8]) if len(a) > 8 and a[8] != "-" else None
    rim_t = float(a[9]) if len(a) > 9 and a[9] != "-" else None
    clip = resolve_clip(clippath, REPO)
    cfg = VideoConfig(tracker="flow", rep_gate="relative", ellipse_scale=True,
                      plausibility_gate=True, transit_aware=True,
                      rim_px=rim_px, rim_t=rim_t)
    try:
        reps, meta = VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed, seed_time=seed_time)
        mv = [r["mean_velocity"] for r in reps]
        setmv = float(np.mean(mv)) if mv else float("nan")
        print(f"RESULT {sid} reps={len(reps)} setMV={setmv:.3f} conf={meta.get('track_confidence',0):.2f} "
              f"static={meta.get('static_track_suspect',False)} scale_suspect={meta.get('scale_suspect',False)} "
              f"seed={seed}@{seed_time} rim={rim_px}@{rim_t}", flush=True)
    except Exception as e:
        print(f"RESULT {sid} ERR {type(e).__name__}: {e} seed={seed}@{seed_time}", flush=True)


if __name__ == "__main__":
    main()
