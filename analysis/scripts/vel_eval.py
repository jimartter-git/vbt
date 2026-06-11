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
sys.path.insert(0, os.path.dirname(__file__))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_analysis.metrics import velocity_loss_pct  # noqa: E402  (THE canonical loss)
from cv_eval import lift_weight  # noqa: E402  (lift-priority weights: main=1.0/secondary=0.5/accessory=0.25)

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


def loss(v, flags=None):
    """The ONE canonical velocity loss (vbt_analysis.metrics): best rep → terminal
    window (mean of last 2). Same number the dataset compare and (mirrored) the Swift
    SetSummary produce — loss is comparable across every tool now."""
    return velocity_loss_pct(v, flags=flags)


def main():
    print(f"{'clip':<15}{'tier':>10}{'pick':>8}{'rel':>5}{'Vit_loss':>9}{'SB_loss':>8}{'OUR_loss':>9}")
    rows = []                                     # (our_err, sb_err_or_nan, weight) on reliable clips
    for sid, path in GT_CLIPS.items():
        vit = vmv(sid, "vitruve")
        if len(vit) < 3:
            continue
        sbv = vmv(sid, "smartbarbell")
        tier, w = lift_weight(sid)
        reps, meta = VideoVelocitySource(VideoConfig(tracker="auto")).estimate(os.path.join(REPO, path))
        our = [r["mean_velocity"] for r in reps]
        rel = bool(meta.get("velocity_reliable", False))
        vl, sl = loss(vit), loss(sbv)
        ol = loss(our, flags=[r.get("flag") for r in reps])
        if rel and ol == ol:                      # we only report (and are scored) when reliable
            rows.append((abs(ol - vl), abs(sl - vl) if sl == sl else float("nan"), w))
        print(f"{sid:<15}{tier:>10}{meta.get('auto_pick','?'):>8}{('Y' if rel else '-'):>5}"
              f"{vl:>9.1f}{(sl if sl == sl else float('nan')):>8.1f}{(ol if ol == ol else float('nan')):>9.1f}")

    def _u(vals):                                 # unweighted mean
        vals = [v for v in vals if v == v]
        return np.mean(vals) if vals else float("nan")
    def _w(pairs):                                # lift-weighted mean of (err, weight), nan-safe
        pairs = [(e, w) for e, w in pairs if e == e]
        return (sum(e * w for e, w in pairs) / sum(w for _, w in pairs)) if pairs else float("nan")

    our_all = [(e, w) for e, _, w in rows]
    common = [(oe, se, w) for oe, se, w in rows if se == se]   # clips where BOTH report a loss
    print(f"\nVelocity-LOSS |err vs Vitruve| (pp):")
    print(f"  all {len(our_all)} clips we report — OURS unweighted {_u([e for e,_ in our_all]):.1f}"
          f"  lift-weighted {_w(our_all):.1f}")
    print(f"  apples-to-apples on {len(common)} clips both report —"
          f" OURS {_u([oe for oe,_,_ in common]):.1f} ({_w([(oe,w) for oe,_,w in common]):.1f} wtd)"
          f"  vs  SB {_u([se for _,se,_ in common]):.1f} ({_w([(se,w) for _,se,w in common]):.1f} wtd)")


if __name__ == "__main__":
    main()
