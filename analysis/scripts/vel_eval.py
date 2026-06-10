#!/usr/bin/env python3
"""Velocity benchmark — velocity-LOSS accuracy (the fatigue signal) vs Vitruve, vs SmartBarbell.

Absolute velocity is scale-limited at low resolution (440px diagonal plates read ~2x; device-
grade only on HD, e.g. IB-1 rmse 0.033). The product signal is velocity LOSS, which is
scale-INVARIANT. The no-tap auto path reports a *reliable* velocity only when it picks the FLOW
tracker (smooth); on a detect-fallback (dark plate) it abstains (count-only) rather than report
a confident-wrong velocity. This scores loss-error on the clips where we DO report.

    python analysis/scripts/vel_eval.py
"""
import sys, os, csv
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RM = os.path.join(REPO, "dataset", "rep_metrics.csv")
# clips with Vitruve velocity GT (set_id -> path)
GT_CLIPS = {
    "20260604-SQ-1": "dataset/raw/20260604-SQ-1.mov", "20260604-SQ-3": "dataset/raw/20260604-SQ-3.mov",
    "20260602-SC-1": "dataset/raw/20260602-SC-1.mov",
    "20260605-BN-1": "dataset/raw/20260605-BN-1.mov", "20260605-BN-2": "dataset/raw/20260605-BN-2.mov",
    "20260605-BN-3": "dataset/raw/20260605-BN-3.mov", "20260605-DL-1": "dataset/raw/20260605-DL-1.mov",
    "20260605-DL-2": "dataset/raw/20260605-DL-2.mov", "20260605-DL-3": "dataset/raw/20260605-DL-3.mov",
    "20260609-BN-1": "dataset/raw/20260609-BN-1.mov", "20260609-BN-2": "dataset/raw/20260609-BN-2.mov",
    "20260609-BN-3": "dataset/raw/20260609-BN-3.mov", "20260609-BN-4": "dataset/raw/20260609-BN-4.mov",
}


def vmv(sid, vendor):
    rs = [r for r in csv.DictReader(open(RM)) if r["set_id"] == sid and r["vendor"] == vendor
          and r["metric"] == "mean_velocity" and (r["flag"] or "") != "phantom"]
    rs.sort(key=lambda r: int(r["rep_index"]))
    return [float(r["value"]) for r in rs]


def loss(v):   # best rep -> mean of last 2 (robust to single-rep noise), %
    return (max(v) - np.mean(v[-2:])) / max(v) * 100 if len(v) >= 3 else float("nan")


def main():
    print(f"{'clip':<15}{'pick':>8}{'rel':>5}{'Vit_loss':>9}{'SB_loss':>8}{'OUR_loss':>9}")
    our_le, sb_le = [], []
    for sid, path in GT_CLIPS.items():
        vit = vmv(sid, "vitruve")
        if len(vit) < 3:
            continue
        sbv = vmv(sid, "smartbarbell")
        reps, meta = VideoVelocitySource(VideoConfig(tracker="auto")).estimate(os.path.join(REPO, path))
        our = [r["mean_velocity"] for r in reps]
        rel = bool(meta.get("velocity_reliable", False))
        vl, sl, ol = loss(vit), loss(sbv), loss(our)
        if rel and ol == ol:                      # we only report (and are scored) when reliable
            our_le.append(abs(ol - vl))
            if sl == sl:
                sb_le.append(abs(sl - vl))        # compare on the SAME clips we report
        print(f"{sid:<15}{meta.get('auto_pick','?'):>8}{('Y' if rel else '-'):>5}"
              f"{vl:>9.1f}{(sl if sl == sl else float('nan')):>8.1f}{(ol if ol == ol else float('nan')):>9.1f}")
    print(f"\nVelocity-LOSS |err vs Vitruve| on the {len(our_le)} clips we report a reliable velocity:")
    print(f"  OURS {np.mean(our_le):.1f}pp   SmartBarbell {np.mean(sb_le):.1f}pp")


if __name__ == "__main__":
    main()
