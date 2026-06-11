#!/usr/bin/env python3
"""CV regression scoreboard — the standalone-competitor benchmark.

Runs our CV stack over every dataset clip that has a ground-truth rep count and
prints a scoreboard: rep COUNT and mean velocity per tracker, against Vitruve
(ground truth) and the commercial app (SmartBarbell/Stance) it must beat.

This is the measurable target for "make CV great": each robustness change is
judged here, and the corpus grows as new clips are added (just extend CLIPS).

    python analysis/scripts/cv_eval.py                 # all clips, default config
    python analysis/scripts/cv_eval.py --set 20260604-SQ-1
    python analysis/scripts/cv_eval.py --adaptive      # use relative rep gating

Seeds are the manual bboxes found by gridding frame 0 (see git history). A clip
with seed=None uses the pose (seed-free) path.
"""
from __future__ import annotations
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.plates import ScaleSpec  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS_CSV = os.path.join(REPO, "dataset", "rep_metrics.csv")

# set_id -> (clip path rel to repo, {tracker: seed_bbox or None}, note, band=(x0,x1) or None,
#            [optional] scale={"angle","plate","kind"} for the --scale (angle-aware) mode)
# EVERY registered clip with a ground-truth count lives here — the complete board.
# NOTE: angle/speed/framing vary PER CLIP (deliberately, to stress generalization) — never
# assume a lift-day is uniform. The `scale` dict is the lifter-confirmed per-clip metadata
# (angle/plate/kind), confirmed 2026-06-05.
CLIPS = {
    # --- device-grade / good clips (regression guards: must stay at GT) ---
    "20260528-IB-1": ("dataset/raw/20260528-IB-1.mp4",
                      {"flow": (323, 163, 316, 316)},
                      "incline bench 185lb - DEVICE-GRADE (rmse 0.033 vs Stance)", (295, 720),
                      {"angle": "side", "plate": 45, "kind": "iron"}),   # iron 45+25; rim=45
    "20260601-ROW-1": ("dataset/raw/20260601-ROW-1.mp4",
                       {"flow": (200, 690, 270, 270)}, "barbell row, side (good clip)", None,
                       {"angle": "side", "plate": 45, "kind": "bumper"}),
    "20260601-ROW-2": ("dataset/raw/20260601-ROW-2.mp4",
                       {"flow": (300, 660, 260, 250)}, "barbell row, angle (good clip)", None,
                       {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    "20260601-ROW-3": ("dataset/raw/20260601-ROW-3.mp4",
                       {"flow": (415, 615, 120, 150)}, "barbell row, front (good clip)", None,
                       {"angle": "front", "plate": 45, "kind": "bumper"}),
    # --- hard clips ---
    "20260604-SQ-1": ("dataset/raw/20260604-SQ-1.mov",
                      {"flow": (192, 72, 90, 90)}, "squat set1, mirror/rack, low-res", None,
                      {"angle": "side", "plate": 45, "kind": "bumper"}),
    "20260604-SQ-3": ("dataset/raw/20260604-SQ-3.mov",
                      {"flow": (165, 77, 110, 110)}, "squat set3, fast TnG (adversarial)", None,
                      {"angle": "side", "plate": 45, "kind": "bumper"}),
    "20260602-SC-1": ("dataset/raw/20260602-SC-1.mov",
                      {"flow": (152, 172, 84, 84, 19.4), "pose": None},
                      "DB press - ANY-FRAME tap on the DB head at a sharp late lockout: 11/11 "
                      "(track verified end-to-end; a frame-0 seed drifts off the DB late-set "
                      "and reads 10 + corrupt loss). --gate to reproduce.", None),
    "20240531-DL-1": ("dataset/raw/20240531-DL-1.mp4",
                      {"flow": (600, 580, 200, 200)},
                      "deadlift ~355lb, bumper plates, front-quarter (CV+SmartBarbell agree 2 reps)", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    # --- 2026-06-05 BN+DL, 135lb, low-res 440px web clips (Vitruve GT; SmartBarbell=video-CV competitor) ---
    "20260605-BN-1": ("dataset/raw/20260605-BN-1.mov",
                      {"flow": (250, 385, 128, 128)}, "bench 135lb set1, diagonal, 440px - flow 10/10 (seed FIX: blue BAR plate, not the rack plates); vel ~2x (circular Hough under-measures the diagonal-ellipse plate)", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    "20260605-BN-2": ("dataset/raw/20260605-BN-2.mov",
                      {"flow": (278, 402, 132, 132)}, "bench 135lb set2, diagonal, 440px - flow 10/10; vel ~2x (ellipse scale)", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    "20260605-BN-3": ("dataset/raw/20260605-BN-3.mov",
                      {"flow": (286, 368, 140, 140)}, "bench 135lb set3 (11 reps), diagonal, 440px - flow 11/11; vel ~2x (ellipse scale)", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    "20260605-DL-1": ("dataset/raw/20260605-DL-1.mov",
                      {"flow": (170, 722, 170, 170)}, "deadlift 135lb set1, front-quarter 440px - flow 10/10 (seed FIX: blue plate); pose(wrist+forearm) also 10/10 @0.81 vs Vit 0.96", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    "20260605-DL-2": ("dataset/raw/20260605-DL-2.mov",
                      {"flow": (150, 722, 184, 184)}, "deadlift 135lb set2, diagonal 440px - flow 10/10 (beats SB=2); pose@0.92 vs Vit 0.98", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    "20260605-DL-3": ("dataset/raw/20260605-DL-3.mov",
                      {"flow": (160, 710, 180, 180)}, "deadlift 135lb set3, diagonal 440px - flow 10/10 (beats SB=6); pose@0.78 vs Vit 0.82", None,
                      {"angle": "diagonal", "plate": 45, "kind": "bumper"}),
    # --- 2026-06-08 barbell rows (dark IRON, front) + 2026-06-09 heavy bench (dark iron) ---
    # detect: None = the shipped AUTO fusion path. flow seeds = the verified LLM-tap seeds
    # (2026-06-11 tap experiment; run with --gate to reproduce its counts — the tap config
    # includes the plausibility gate).
    "20260608-ROW-1": ("dataset/raw/060826_row1.mov", {"flow": (90, 352, 85, 85), "detect": None},
                       "row TnG, front, dark iron - LLM-tap 10/10 (1 tap, --gate)", None),
    "20260608-ROW-2": ("dataset/raw/060826_row2.mov", {"flow": (105, 480, 80, 80, 9.6), "detect": None},
                       "row TnG, front, dark iron - ANY-FRAME tap, tight box on the plate HUB at "
                       "the bottom hang: 10/10 verified (--gate). Frame-0 taps go static (dark "
                       "iron has no flow texture at rest); the big upper-left disc is a STORED "
                       "plate the working plate sweeps in front of.", None),
    "20260608-ROW-3": ("dataset/raw/060826_row3.mov", {"flow": (85, 335, 110, 110), "detect": None},
                       "row TnG, front, dark iron - LLM-tap 10/10 (--gate)", None),
    "20260608-ROW-4": ("dataset/raw/060826_row4.mov", {"detect": None},
                       "row TnG, dead-front (hardest) - UNTAPPABLE: working plates edge-on, "
                       "big disc = rack decoy (verified again 2026-06-11); auto is best", None),
    "20260609-BN-1": ("dataset/raw/20260609-BN-1.mov", {"flow": (28, 285, 100, 100, 15.0), "detect": None},
                      "bench 205lb, dark iron - ANY-FRAME tap at a sharp lockout: 10/10 verified, "
                      "ROM steady ~30cm, MV 0.43->0.24 vs Vitruve 0.49->0.26 (near device-grade "
                      "on dark iron!). Frame-0 tap read 9. --gate.", None),
    "20260609-BN-2": ("dataset/raw/20260609-BN-2.mov", {"flow": (52, 345, 95, 95, 12.5), "detect": None},
                      "bench 195lb, dark iron - ANY-FRAME tap: 10/10 verified, MV 0.44->0.32 vs "
                      "Vitruve 0.41->0.33, loss err 1.2pp (frame-0 tap: 7.8pp). --gate.", None),
    "20260609-BN-3": ("dataset/raw/20260609-BN-3.mov", {"flow": (66, 402, 76, 76), "detect": None},
                      "bench 200lb, dark iron - LLM-tap 10/10 (1 tap, --gate)", None),
    "20260609-BN-4": ("dataset/raw/20260609-BN-4.mov", {"flow": (33, 277, 105, 105, 14.0), "detect": None},
                      "bench 205lb near-failure, dark iron - ANY-FRAME tap: 10/10 verified, the "
                      "grind curve intact (MV 0.28->0.12 vs Vitruve 0.30->0.17, loss err 1.8pp; "
                      "the frame-0 tap counted 10 but read loss 7% vs 45%). Track follows the "
                      "plate INTO the rack; the plausibility gate drops the racking moves. --gate.", None),
    # --- 2026-06-10 Equinox squats + RDLs (hex iron, mirror; Vitruve crashed -> GT = lifter
    # count in sets.csv actual_reps; SB counts in set notes only, not per-rep rows) ---
    "20260610-SQ-1": ("dataset/raw/061026-SQ1.mov", {"flow": (190, 305, 80, 80)},
                      "squat 225lb set1, Equinox hex+mirror 60fps - LLM-tap 10/10 (1 tap); auto 10/10", None),
    "20260610-SQ-4": ("dataset/raw/061026-SQ4.mov", {"flow": (95, 320, 90, 90)},
                      "squat 225lb set4, Equinox hex - LLM-tap 10/10 (1 tap); auto 10/10", None),
    "20260610-RDL-1": ("dataset/raw/061026-RDL1.mov", {"flow": (265, 510, 130, 130, 11.0)},
                       "RDL 225lb set1 - ANY-FRAME tap on the plate at a rep BOTTOM (frame-0 is "
                       "untappable: plate fused with the lifter + post; frame-0 taps body-lock, "
                       "lifter-caught). 7/8 with a VERIFIED dead-on plate track - the 8th is "
                       "segmentation (auto agrees at 7). --gate.", None),
    "20260610-RDL-2": ("dataset/raw/061026-RDL2.mov", {"flow": (278, 503, 125, 125, 9.0)},
                       "RDL 225lb set2 - ANY-FRAME tap at the standing pause: 8/8 verified "
                       "(post-occlusion clips ROM on the 2 deepest reps). Frame-0 = body-lock "
                       "trap, see RDL-1. --gate.", None),
}


# Reference trust order: Vitruve (ground truth) > on-bar BLE apps. The highest-priority
# vendor present is the GT reference; the next is shown as the competitor to beat.
_REF_PRIORITY = ["vitruve", "stance", "smartbarbell", "metric"]


# Lift priority for backtest scoring. We must get the MAIN barbell lifts (squat / bench /
# deadlift) right FIRST — that's the product's core. Rows + RDLs matter, but less; isolation /
# accessory work (skull crushers, DB press) matters least. Full fusion (watch + video + human
# editor) will eventually handle everything, but the CV backtest weights the mean error toward
# the lifts that matter most, so a regression on squat costs more than one on a skull crusher.
# Weights are deliberately gentle ("affect scoring a bit") and easy to tune.
_LIFT_TIER = {                 # set_id lift-code -> (tier, weight)
    "SQ": ("main", 1.0), "BN": ("main", 1.0), "IB": ("main", 1.0), "DL": ("main", 1.0),
    "ROW": ("secondary", 0.5), "RDL": ("secondary", 0.5),
    "SC": ("accessory", 0.25),
}


def lift_weight(set_id):
    """(tier, weight) for a set_id like '20260604-SQ-1' — middle token is the lift code.
    RDL is matched before DL because it's its own token. Unknown lifts default to secondary."""
    code = set_id.split("-")[1] if "-" in set_id else ""
    return _LIFT_TIER.get(code, ("secondary", 0.5))


def gt_counts(set_id):
    """(ref_count, ref_mean, competitor_label, competitor_count) from the DB — falls back
    to the best on-bar app when there's no Vitruve row (e.g. the row clips)."""
    rows = [r for r in csv.DictReader(open(REPS_CSV))
            if r["set_id"] == set_id and r["metric"] == "mean_velocity"
            and (r["rep_index"] or "").strip()]   # blank rep_index = SET-level row, not a rep
    out = {}
    for r in rows:
        out.setdefault(r["vendor"], []).append(r)
    def real(v):  # drop phantom rows
        return [x for x in out.get(v, []) if (x["flag"] or "") != "phantom"]
    present = [v for v in _REF_PRIORITY if real(v)]
    ref = present[0] if present else None
    comp = present[1] if len(present) > 1 else None
    rmean = (sum(float(x["value"]) for x in real(ref)) / len(real(ref))) if ref else float("nan")
    return (len(real(ref)) if ref else 0, rmean, comp, len(real(comp)) if comp else 0)


def run(clip, tracker, seed, adaptive, occlusion=False, band=None, scale=None, gate=False):
    spec = None
    if scale and tracker != "pose":      # plate scale is N/A for the pose/seed-free path
        spec = ScaleSpec(top_plate=scale["plate"], kind=scale["kind"], angle=scale["angle"])
    seed_time = None
    if seed is not None and len(seed) == 5:      # (x,y,w,h,t) = tap-on-ANY-frame seed
        seed, seed_time = tuple(seed[:4]), float(seed[4])
    cfg = VideoConfig(tracker=tracker, rep_gate=("relative" if adaptive else "absolute"),
                      occlusion_robust=(occlusion and tracker == "flow"), band=band,
                      scale_spec=spec, plausibility_gate=gate)
    reps, meta = VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed, seed_time=seed_time)
    mv = [r["mean_velocity"] for r in reps]
    return (len(reps), (sum(mv) / len(mv) if mv else float("nan")),
            meta["track_confidence"], meta.get("scale_suspect", False),
            meta.get("static_track_suspect", False))


def _sb_count(sid):
    """SmartBarbell's reported rep count from the DB = its non-phantom mean_velocity rows
    (undercount-flagged reps ARE reps SB logged; phantom = a dropped rep)."""
    reps = set()
    for r in csv.DictReader(open(REPS_CSV)):
        if (r["set_id"] == sid and r["vendor"] == "smartbarbell"
                and r["metric"] == "mean_velocity" and (r["flag"] or "") != "phantom"
                and (r["rep_index"] or "").strip()):   # skip set-level rows
            reps.add(r["rep_index"])
    return len(reps) if reps else None


def _true_gt(sid, fallback):
    """True rep count from the lifter's logged set (sets.csv actual_reps) — the honest GT,
    needed where the only vendor in the DB undercounts (e.g. rows: Vitruve fails, SB partial).
    Falls back to the vendor-priority count."""
    p = os.path.join(REPO, "dataset", "sets.csv")
    try:
        for r in csv.DictReader(open(p)):
            if r["set_id"] == sid and r.get("actual_reps", "").strip():
                return int(r["actual_reps"])
    except Exception:
        pass
    return fallback


def _auto_board(sets):
    """The 'no human in the loop' scoreboard — the SHIPPED auto path (`tracker='detect'`,
    seed-free track-by-detection) vs ground truth and SmartBarbell. This is the metric that
    matters for the product: counts with NO tap. (The default board uses manual seeds = the
    one-tap UX, which does better; see docs/cv-fusion.md.)"""
    print("\nCV AUTO scoreboard — NO seed, shipped AUTO fusion (flow⊕detect) — count(Δ vs GT) · vs SmartBarbell\n")
    hdr = f"{'set':<16}{'tier':>10}{'GT':>4}{'SB':>5}{'DETECT':>9}{'|e|':>5}{'SB|e|':>6}"
    print(hdr); print("-" * len(hdr))
    import numpy as _np
    oe = []; se = []                 # lists of (err, weight)
    for sid in sets:
        clip = os.path.join(REPO, CLIPS[sid][0])
        refn, _, _, _ = gt_counts(sid)
        gt = _true_gt(sid, refn)
        sbn = _sb_count(sid)
        tier, w = lift_weight(sid)
        try:
            n, mean, conf, suspect, static = run(clip, "auto", None, True, False, None, None)
            cell = f"{n}({n - gt:+d})"; err = abs(n - gt)
        except Exception as e:
            cell = f"ERR({type(e).__name__})"; err = gt
        oe.append((err, w))
        sbe = abs(sbn - gt) if sbn is not None else None
        if sbe is not None: se.append((sbe, w))
        print(f"{sid:<16}{tier:>10}{gt:>4}{('-' if sbn is None else sbn):>5}{cell:>9}"
              f"{err:>5}{('-' if sbe is None else sbe):>6}")
    def _u(p): return _np.mean([e for e, _ in p]) if p else float("nan")
    def _w(p): return (sum(e * w for e, w in p) / sum(w for _, w in p)) if p else float("nan")
    print(f"\nUNWEIGHTED mean|err|  = OURS {_u(oe):.2f}   SmartBarbell {_u(se):.2f} (on its {len(se)} clips)")
    print(f"LIFT-WEIGHTED mean|err| = OURS {_w(oe):.2f}   SmartBarbell {_w(se):.2f}   "
          f"(main=1.0 / secondary[row,RDL]=0.5 / accessory[SC]=0.25 — see lift_weight())")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", dest="only")
    ap.add_argument("--adaptive", action="store_true", help="relative (adaptive) rep gating")
    ap.add_argument("--occlusion", action="store_true", help="flow coast + re-acquire")
    ap.add_argument("--gate", action="store_true",
                    help="enable the rep-plausibility gate on the seeded paths (the tap-UX "
                         "config; the auto path always applies it post-selection)")
    ap.add_argument("--scale", action="store_true",
                    help="angle-aware px→m via each clip's plate+angle (ScaleSpec); "
                         "side=trusted, diagonal=anchored+lower conf, front=relative-only")
    ap.add_argument("--auto", action="store_true",
                    help="PRODUCTION-REALISTIC eval: ignore the manual seeds and run the "
                         "automated paths only — flow with auto_seed_bbox + seed-free pose. "
                         "This is 'how well does it work with NO human tapping the plate'.")
    args = ap.parse_args()

    if args.auto:
        _auto_board([args.only] if args.only else list(CLIPS))
        return

    sets = [args.only] if args.only else list(CLIPS)
    print(f"\nCV scoreboard{' [adaptive gate]' if args.adaptive else ''}"
          f"{' [angle-aware scale]' if args.scale else ''} "
          f"— rep count (Δ vs Vitruve) · mean m/s · track-conf\n")
    hdr = f"{'set':<16}{'GT':>4}{'comp':>14}{'tracker':>9}{'reps':>8}{'mean':>7}{'conf':>7}  note"
    print(hdr); print("-" * len(hdr))
    for sid in sets:
        clip_rel, trackers, note, band = CLIPS[sid][:4]
        scale = CLIPS[sid][4] if args.scale and len(CLIPS[sid]) > 4 else None
        clip = os.path.join(REPO, clip_rel)
        gtn, gtmean, comp, compn = gt_counts(sid)
        if not gtn:                        # no per-rep GT rows → the lifter's logged count
            gtn = _true_gt(sid, gtn)
        compstr = f"{comp[:5]}={compn}" if comp else "-"
        first = True
        for tracker, seed in trackers.items():
            rownote = note if first else ""
            try:
                n, mean, conf, suspect, static = run(clip, tracker, seed, args.adaptive,
                                                     args.occlusion, band, scale, args.gate)
                delta = f"{n}({n - gtn:+d})"
                meanstr = (f"{mean:.2f}?" if suspect else f"{mean:.2f}")   # ? = scale flagged
                # A barely-moving but confident track = seed on a STATIC object (rack/background
                # plate), NOT a CV failure. Shout it so it's never silently read as "CV can't".
                if static:
                    rownote = ("⚠ STATIC-SEED: track barely moves — seed is likely on a "
                               "rack-stored/background plate, NOT the working bar plate; "
                               "re-seed & re-run (see analysis/CV_ONBOARDING.md). " + rownote)
            except Exception as e:
                delta, meanstr, conf = f"ERR", "-", 0.0
                rownote = rownote + f" [{type(e).__name__}: {e}]"
            lead = f"{sid:<16}{gtn:>4}{compstr:>14}" if first else " " * 34
            print(f"{lead}{tracker:>9}{delta:>8}{meanstr:>7}{conf:>7.2f}  {rownote}")
            first = False


if __name__ == "__main__":
    main()
