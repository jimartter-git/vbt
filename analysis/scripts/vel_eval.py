#!/usr/bin/env python3
"""Velocity benchmark — velocity-LOSS (the fatigue signal) AND ABSOLUTE velocity
vs Vitruve, vs SmartBarbell.

Two estimator modes:
    python analysis/scripts/vel_eval.py          # auto (no tap, shipped fusion)
    python analysis/scripts/vel_eval.py --tap    # registered one-tap seeds (CLIPS
                                                 # flow seeds, --gate config; the
                                                 # human-grade path)

Scores, per clip with Vitruve per-rep GT:
  * velocity LOSS |err| (canonical, vbt_analysis.metrics) — scale-invariant, the
    product signal; the auto path is only scored where it reports reliable velocity.
  * ABSOLUTE set mean velocity |err| (m/s) and per-rep RMSE on count-matched clips —
    the OPEN metric (SmartBarbell ≈ 0.07 set-MV |err|; printed from the DB as the
    bar). Lift-weighted summaries are the decision metric (learning #15).
"""
import sys, os, csv, argparse
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_analysis.metrics import velocity_loss_pct  # noqa: E402  (THE canonical loss)
from cv_eval import lift_weight, CLIPS, RIM_PX, PLATE_COLOR  # noqa: E402

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
    "20260616-BN-1": "dataset/raw/20260616-BN_1.mov", "20260616-BN-2": "dataset/raw/20260616-BN_2.mov",
    "20260616-BN-3": "dataset/raw/20260616-BN_3.mov", "20260616-BN-4": "dataset/raw/20260616-BN_4.mov",
    "20260616-BN-5": "dataset/raw/20260616-BN_5.mov",
}


def vmv(sid, vendor):
    rs = [r for r in csv.DictReader(open(RM)) if r["set_id"] == sid and r["vendor"] == vendor
          and r["metric"] == "mean_velocity" and (r["flag"] or "") != "phantom"
          and (r["rep_index"] or "").strip()]
    rs.sort(key=lambda r: int(r["rep_index"]))
    return [float(r["value"]) for r in rs]


def loss(v, flags=None):
    """The ONE canonical velocity loss (vbt_analysis.metrics): best rep → terminal
    window (mean of last 2). Same number the dataset compare and (mirrored) the Swift
    SetSummary produce — loss is comparable across every tool now."""
    return velocity_loss_pct(v, flags=flags)


def _estimate(sid, path, tap):
    """(rep mvs, flags, velocity_reliable) for the chosen estimator mode."""
    from vbt_video.clip_store import resolve_clip   # R2 masters resolve to the local cache
    clip = resolve_clip(path, REPO)
    if tap:
        seed = CLIPS[sid][1].get("flow")
        if seed is None:                       # untappable clip → no tap row
            return None, None, False
        band = CLIPS[sid][3]
        seed_time = None
        if len(seed) == 5:
            seed, seed_time = tuple(seed[:4]), float(seed[4])
        rp = RIM_PX.get(sid)
        rim_px, rim_t = (rp if rp is not None else (None, None))
        # NOTE: depth_scale (the continuous-ruler tier) is EXPERIMENTAL default-OFF after
        # the 2026-06-12 attempts (see cv-fusion postmortem): the 440px traces conflate
        # mask-fraction/mode-switch variation with true perspective. Constant rim ships.
        cfg = VideoConfig(tracker="flow", rep_gate="relative", ellipse_scale=True,
                          plausibility_gate=True, transit_aware=True, band=band,
                          rim_px=rim_px, rim_t=rim_t)
        reps, meta = VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed, seed_time=seed_time)
        rel = True                             # tap tracks are visually verified
    else:
        reps, meta = VideoVelocitySource(VideoConfig(tracker="auto")).estimate(clip)
        rel = bool(meta.get("velocity_reliable", False))
    return [r["mean_velocity"] for r in reps], [r.get("flag") for r in reps], rel


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tap", action="store_true",
                    help="score the registered one-tap seeds (CLIPS, --gate config) "
                         "instead of the auto path")
    args = ap.parse_args()
    mode = "TAP" if args.tap else "AUTO"

    print(f"[{mode}] {'clip':<15}{'tier':>10}{'rel':>5}{'Vit_loss':>9}{'SB_loss':>8}"
          f"{'OUR_loss':>9} | {'Vit_MV':>7}{'SB_MV':>7}{'OUR_MV':>7}{'rRMSE':>7}")
    lrows, arows = [], []        # loss: (our_err, sb_err, w) · abs: (our_err, sb_err, rmse, w)
    for sid, path in GT_CLIPS.items():
        vit = vmv(sid, "vitruve")
        if len(vit) < 3:
            continue
        sbv = vmv(sid, "smartbarbell")
        tier, w = lift_weight(sid)
        our, flags, rel = _estimate(sid, path, args.tap)
        if our is None:
            continue
        vl, sl = loss(vit), loss(sbv)
        ol = loss(our, flags=flags)
        if rel and ol == ol:
            lrows.append((abs(ol - vl), abs(sl - vl) if sl == sl else float("nan"), w))
        # --- absolute velocity ---
        vmv_set = float(np.mean(vit))
        omv_set = float(np.mean(our)) if our else float("nan")
        smv_set = float(np.mean(sbv)) if len(sbv) >= 3 else float("nan")
        rmse = (float(np.sqrt(np.mean((np.array(our) - np.array(vit)) ** 2)))
                if rel and len(our) == len(vit) else float("nan"))
        o_err = abs(omv_set - vmv_set) if omv_set == omv_set else float("nan")
        s_err = abs(smv_set - vmv_set) if smv_set == smv_set else float("nan")
        if rel and o_err == o_err:
            arows.append((o_err, s_err, rmse, w))
        # per-clip verdict: W/L vs SB, and the success bar (≤ SB err or ≤0.05, the harder)
        bar = min(s_err, 0.05) if s_err == s_err else 0.05
        wl = ("W" if o_err <= s_err else "L") if (o_err == o_err and s_err == s_err) else "·"
        verdict = (f"{wl}{'✓' if o_err <= bar + 1e-9 else '✗'}"
                   if o_err == o_err and tier == "main" else " ")
        print(f"{sid:<15}{tier:>10}{('Y' if rel else '-'):>5}"
              f"{vl:>9.1f}{(sl if sl == sl else float('nan')):>8.1f}{(ol if ol == ol else float('nan')):>9.1f}"
              f" | {vmv_set:>7.2f}{(smv_set if smv_set == smv_set else float('nan')):>7.2f}"
              f"{(omv_set if omv_set == omv_set else float('nan')):>7.2f}"
              f"{(rmse if rmse == rmse else float('nan')):>7.2f}  {verdict}", flush=True)

    def _u(vals):
        vals = [v for v in vals if v == v]
        return np.mean(vals) if vals else float("nan")
    def _w(pairs):
        pairs = [(e, w) for e, w in pairs if e == e]
        return (sum(e * w for e, w in pairs) / sum(w for _, w in pairs)) if pairs else float("nan")

    common = [(oe, se, w) for oe, se, w in lrows if se == se]
    print(f"\n[{mode}] velocity-LOSS |err vs Vitruve| (pp):")
    print(f"  all {len(lrows)} reported — OURS {_u([e for e,_,_ in lrows]):.1f} unweighted"
          f", {_w([(e,w) for e,_,w in lrows]):.1f} lift-weighted")
    print(f"  apples-to-apples ({len(common)} clips both report) —"
          f" OURS {_u([oe for oe,_,_ in common]):.1f} ({_w([(oe,w) for oe,_,w in common]):.1f} wtd)"
          f"  vs SB {_u([se for _,se,_ in common]):.1f} ({_w([(se,w) for _,se,w in common]):.1f} wtd)")
    acommon = [(oe, se, w) for oe, se, _, w in arows if se == se]
    print(f"\n[{mode}] ABSOLUTE set-MV |err vs Vitruve| (m/s) — the OPEN metric:")
    print(f"  all {len(arows)} reported — OURS {_u([e for e,_,_,_ in arows]):.3f} unweighted"
          f", {_w([(e,w) for e,_,_,w in arows]):.3f} lift-weighted")
    print(f"  apples-to-apples ({len(acommon)} clips) —"
          f" OURS {_u([oe for oe,_,_ in acommon]):.3f} ({_w([(oe,w) for oe,_,w in acommon]):.3f} wtd)"
          f"  vs SB {_u([se for _,se,_ in acommon]):.3f} ({_w([(se,w) for _,se,w in acommon]):.3f} wtd)")
    print(f"  per-rep RMSE (count-matched clips): {_u([r for _,_,r,_ in arows]):.3f} unweighted"
          f", {_w([(r,w) for _,_,r,w in arows]):.3f} lift-weighted")


if __name__ == "__main__":
    main()
