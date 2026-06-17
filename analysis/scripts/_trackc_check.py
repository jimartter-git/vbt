"""Track C no-regression + honesty-gate check (local clips, one pass).

Runs the seed-free AUTO path with the honesty gate and reports, per clip: the count, the
PRE-gate count (best confidence×regularity pick, = old behaviour), whether the gate FLIPPED
the pick, the honesty verdict, and Δ vs ground truth. A count regresses only when the gate
flips a pick, so `flip=False` everywhere ⇒ counts byte-identical to the pre-gate baseline.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402

# import the corpus + GT helpers from the main board
import cv_eval  # noqa: E402

REPO = cv_eval.REPO


def main():
    only = sys.argv[1:] or None
    sets = only or list(cv_eval.CLIPS)
    print(f"\nTrack C honesty-gate check — seed-free AUTO (gate ON)\n")
    hdr = f"{'set':<16}{'tier':>10}{'GT':>4}{'reps':>6}{'pre':>5}{'flip':>6}{'honest':>8}  flags"
    print(hdr); print("-" * len(hdr))
    flips = 0; regress = []
    for sid in sets:
        rel = cv_eval.CLIPS[sid][0]
        try:
            clip = resolve_clip(rel, REPO)
        except Exception as e:
            print(f"{sid:<16}  [unavailable: {type(e).__name__}]"); continue
        refn, _, _, _ = cv_eval.gt_counts(sid)
        gt = cv_eval._true_gt(sid, refn)
        tier, _ = cv_eval.lift_weight(sid)
        try:
            reps, meta = VideoVelocitySource(VideoConfig(tracker="auto")).estimate(clip)
        except Exception as e:
            print(f"{sid:<16}{tier:>10}{gt:>4}  ERR {type(e).__name__}: {e}"); continue
        n = len(reps); pre = meta.get("count_pre_gate")
        flip = meta.get("honesty_flipped_pick", False)
        h = meta.get("track_honesty", {})
        pick = meta.get("auto_pick")
        flips += int(bool(flip))
        if flip and pre is not None and abs(n - gt) > abs(pre - gt):
            regress.append((sid, pre, n, gt))
        print(f"{sid:<16}{tier:>10}{gt:>4}{n:>4}({n-gt:+d}){str(pre):>5}{str(bool(flip)):>6}"
              f"{str(h.get('honest')):>8}  {pick};{','.join(h.get('flags', []))}")
    print(f"\nflips={flips}  (count changes only on a flip)")
    if regress:
        print("⚠ REGRESSIONS (gate moved count further from GT):")
        for sid, pre, n, gt in regress:
            print(f"   {sid}: {pre}→{n} (GT {gt})")
    else:
        print("✓ no flip worsened a count vs the pre-gate pick")


if __name__ == "__main__":
    main()
