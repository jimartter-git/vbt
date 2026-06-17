#!/usr/bin/env python3
"""Print auto seed candidates (moving circles) in NATIVE upright coords + auto-seed.

Usage: python3 _candidates.py CLIPPATH
"""
import sys, os
import cv2
cv2.setNumThreads(1)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
from vbt_video.frames import PyAVDecoder  # noqa: E402
from vbt_video.track import auto_seed_motion, seed_candidates  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402


def main():
    clip = resolve_clip(sys.argv[1], REPO)
    src = PyAVDecoder(clip)
    try:
        a = auto_seed_motion(src)
        print("auto_seed_motion ->", a, flush=True)
    except Exception as e:
        print("auto_seed_motion ERR", e, flush=True)
    src2 = PyAVDecoder(clip)
    try:
        cands = seed_candidates(src2, topk=8)
        for c in cands:
            print("candidate", c, flush=True)
    except Exception as e:
        print("seed_candidates ERR", e, flush=True)


if __name__ == "__main__":
    main()
