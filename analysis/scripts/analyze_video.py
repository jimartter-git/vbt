#!/usr/bin/env python3
"""Run the meVBT video pipeline on a clip → per-rep velocity, and optionally drop
it into the dataset as vendor `mevbt_cv` so `compare.py` scores us against the
commercial tools on the same set.

Usage:
    python analysis/scripts/analyze_video.py CLIP --set-id 20260528-IB-1 \
        [--seed X,Y,W,H | --auto-seed] [--plate-cm 45] [--append]

Then:  python dataset/tools/compare.py <set-id>
"""
from __future__ import annotations
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS_CSV = os.path.join(REPO, "dataset", "rep_metrics.csv")
RH = ["set_id", "vendor", "rep_index", "true_rep", "metric", "value", "unit", "flag", "confidence"]
UNIT = {"mean_velocity": "m/s", "peak_velocity": "m/s", "rom": "cm"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("clip")
    p.add_argument("--set-id", required=True)
    p.add_argument("--seed", help="X,Y,W,H bbox around the plate in frame 0")
    p.add_argument("--auto-seed", action="store_true", help="detect the plate automatically")
    p.add_argument("--plate-cm", type=float, default=45.0)
    p.add_argument("--append", action="store_true", help="write rows to dataset/rep_metrics.csv")
    args = p.parse_args()

    seed = None
    if args.seed:
        seed = tuple(float(v) for v in args.seed.split(","))
        if len(seed) != 4:
            p.error("--seed must be X,Y,W,H")

    src = VideoVelocitySource(VideoConfig(plate_m=args.plate_cm / 100.0))
    reps, meta = src.estimate(args.clip, seed_bbox=seed)

    print(f"\n{args.set_id}  via mevbt_cv ({args.clip})")
    print(f"  {meta['n_frames']} frames @ {meta['fps']} fps · scale {meta['m_per_px']*100:.3f} cm/px "
          f"· track-confidence {meta['track_confidence']} · seed {meta['seed_bbox']}")
    print(f"  {'rep':>3}  {'mean':>6}  {'peak':>6}  {'rom(cm)':>7}")
    for r in reps:
        print(f"  {r['rep_index']:>3}  {r['mean_velocity']:>6.3f}  {r['peak_velocity']:>6.3f}  {r['rom']:>7.1f}")
    print(f"  → {len(reps)} concentric reps")

    if args.append:
        rows = []
        for r in reps:
            for m in ("mean_velocity", "peak_velocity", "rom"):
                rows.append(dict(set_id=args.set_id, vendor="mevbt_cv",
                                 rep_index=r["rep_index"], true_rep=r["rep_index"],
                                 metric=m, value=r[m], unit=UNIT[m], flag="",
                                 confidence=meta["track_confidence"]))
        new = not os.path.exists(REPS_CSV)
        with open(REPS_CSV, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=RH)
            if new:
                w.writeheader()
            w.writerows(rows)
        print(f"  appended {len(rows)} rows to {REPS_CSV} as vendor=mevbt_cv")
        print(f"  → python dataset/tools/compare.py {args.set_id}")
    else:
        print("  (dry run — pass --append to score against the other tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
