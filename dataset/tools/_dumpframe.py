#!/usr/bin/env python3
"""Dump an UPRIGHT frame (and optional seed-overlay) at time t for visual seeding.

Usage: python3 _dumpframe.py CLIPPATH t_seconds OUTPNG [x y w h]
Optionally also draws a crosshair grid every 200px and labels.
"""
import sys, os
import cv2
cv2.setNumThreads(1)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
from vbt_video.frames import PyAVDecoder  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402


def main():
    clippath = sys.argv[1]
    t = float(sys.argv[2])
    out = sys.argv[3]
    seed = None
    if len(sys.argv) >= 8:
        seed = tuple(int(v) for v in sys.argv[4:8])
    clip = resolve_clip(clippath, REPO)
    dec = PyAVDecoder(clip)
    fps = dec.fps
    target = int(round(t * fps))
    frame = None
    for i, fr in enumerate(dec):
        if i == target:
            frame = fr.img.copy()
            break
    if frame is None:
        print("NO FRAME"); return
    h, w = frame.shape[:2]
    # grid
    for gx in range(0, w, 200):
        cv2.line(frame, (gx, 0), (gx, h), (60, 60, 60), 1)
        cv2.putText(frame, str(gx), (gx + 2, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    for gy in range(0, h, 200):
        cv2.line(frame, (0, gy), (w, gy), (60, 60, 60), 1)
        cv2.putText(frame, str(gy), (2, gy + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if seed:
        x, y, ww, hh = seed
        cv2.rectangle(frame, (x, y), (x + ww, y + hh), (0, 0, 255), 3)
        cv2.circle(frame, (x + ww // 2, y + hh // 2), 4, (0, 0, 255), -1)
    # downscale for viewing if large
    scale = 1.0
    if max(h, w) > 1400:
        scale = 1400.0 / max(h, w)
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    cv2.imwrite(out, frame)
    print(f"WROTE {out} ({w}x{h}, view-scale={scale:.3f}, fps={fps:.1f})", flush=True)


if __name__ == "__main__":
    main()
