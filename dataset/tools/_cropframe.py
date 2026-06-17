#!/usr/bin/env python3
"""Crop a native-coord region from an upright frame at time t (for precise seeding).

Usage: python3 _cropframe.py CLIPPATH t x0 y0 x1 y1 OUTPNG
Coords are NATIVE upright pixels. Draws a 50px grid in the crop.
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
    clippath, t = sys.argv[1], float(sys.argv[2])
    x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7])
    out = sys.argv[7]
    clip = resolve_clip(clippath, REPO)
    dec = PyAVDecoder(clip)
    target = int(round(t * dec.fps))
    frame = None
    for i, fr in enumerate(dec):
        if i == target:
            frame = fr.img.copy(); break
    if frame is None:
        print("NO FRAME"); return
    h, w = frame.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    crop = frame[y0:y1, x0:x1].copy()
    for gx in range(0, x1 - x0, 50):
        cv2.line(crop, (gx, 0), (gx, y1 - y0), (60, 200, 60), 1)
        cv2.putText(crop, str(x0 + gx), (gx + 1, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    for gy in range(0, y1 - y0, 50):
        cv2.line(crop, (0, gy), (x1 - x0, gy), (60, 200, 60), 1)
        cv2.putText(crop, str(y0 + gy), (1, gy + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    # upscale 2x for visibility
    crop = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(out, crop)
    print(f"WROTE {out} region=({x0},{y0},{x1},{y1}) framesize={w}x{h} fps={dec.fps:.1f}", flush=True)


if __name__ == "__main__":
    main()
