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
from vbt_video.clip_store import resolve_clip  # noqa: E402
from vbt_video import honesty as _honesty  # noqa: E402
from vbt_analysis import validation as _prov  # noqa: E402

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
    # --- 2026-06-16 bench press (5x10; set1 225lb top set, sets2-5 205lb back-offs).
    # 1080p60 h264, iPhone frame.rotation=-90 (PyAVDecoder auto-uprights -> 1080x1920; NOT a
    # bug). Dark Rogue DEEP-DISH iron + blue hub, head-on rack view; lifter un/reracks the bar.
    # Westwood Athletics. Vitruve GT + Apple Watch IMU + SmartBarbell. The un/rerack horizontal
    # transit USED to over-count (BN-4/5 = 11) + tank the last-rep velocity; the horizontal-aware
    # merge + transit gate (kinematics.py) fixed it -> AUTO 10/10 EXACT all 5. Velocity needs the
    # human-confirmed RIM (deep-dish 45 ~570px, the hub is ~72px = 7x scale error; see RIM_PX);
    # with it, --tap abs MV RMSE ~0.04 vs Vitruve (matches/beats SmartBarbell). Flow seed = the
    # blue hub at a clear frame (x,y,w,h,t). ---
    "20260616-BN-1": ("dataset/raw/20260616-BN_1.mov", {"flow": (156, 732, 60, 60, 0.3), "detect": None},
                      "bench 225lb top set x10, RPE 7.5 - AUTO 10/10 EXACT; --tap+rim abs RMSE "
                      "0.071, VL 39 vs Vit 42 (3pp)", None),
    "20260616-BN-2": ("dataset/raw/20260616-BN_2.mov", {"flow": (144, 778, 60, 60, 27.3), "detect": None},
                      "bench 205lb x10 - AUTO 10/10 EXACT (transit gate drops the unrack); "
                      "--tap+rim abs RMSE 0.027 (beats SB 0.044), VL 31 vs 24", None),
    "20260616-BN-3": ("dataset/raw/20260616-BN_3.mov", {"flow": (283, 800, 60, 60, 6.0), "detect": None},
                      "bench 205lb x10 - AUTO 10/10 EXACT; --tap+rim abs RMSE 0.035 (beats SB "
                      "0.056), VL 42 vs 30 (per-rep noise)", None),
    "20260616-BN-4": ("dataset/raw/20260616-BN_4.mov", {"flow": (316, 780, 60, 60, 9.3), "detect": None},
                      "bench 205lb x10 - AUTO 10/10 EXACT (was 11: leading unrack, now gated); "
                      "--tap+rim abs RMSE 0.042, VL 44 vs 40 (4pp)", None),
    "20260616-BN-5": ("dataset/raw/20260616-BN_5.mov", {"flow": (363, 927, 60, 60, 24.2), "detect": None},
                      "bench 205lb x10 - AUTO 10/10 EXACT (was 11); --tap+rim abs RMSE 0.023 "
                      "(beats SB 0.033), VL 55 vs 59 (4pp)", None),
    # 06-15 barbell rows (R2 masters, resolve_clip → .clipcache; upright-portrait coords).
    # 1-tap plate/hub seeds verified 10/10 EXACT (auto grabbed rack decoys); rim_px not yet
    # measured, so absolute MV is scale_suspect (inflated) but the COUNT and scale-invariant
    # velocity-LOSS are valid. ROW-3 is 4K (needs a proxy), ROW-5 auto already 10/10.
    "20260615-ROW-1": ("dataset/raw/20260615-ROW-1.mov", {"flow": (600, 1110, 130, 130, 10.0), "detect": None},
                       "row, 1-tap plate seed @10s: 10/10 EXACT (auto failed-decoy). rim_px TBD", None),
    "20260615-ROW-2": ("dataset/raw/20260615-ROW-2.mov", {"flow": (525, 1140, 150, 150, 6.0), "detect": None},
                       "row, 1-tap plate seed @6s: 10/10 EXACT (auto failed-decoy). rim_px TBD", None),
    "20260615-ROW-4": ("dataset/raw/20260615-ROW-4.mov", {"flow": (519, 1215, 150, 150, 6.0), "detect": None},
                       "row, 1-tap plate seed @6s: 10/10 EXACT (auto failed-decoy). rim_px TBD", None),
}


# HUMAN-CONFIRMED plate rim diameters (px) — the "plate confirm/adjust" surface
# (learning #10; measured 2026-06-12 by circle-overlay confirmation on sharp frames,
# like WL Analysis's manual circle). Scale-only override; fixes the hub-vs-rim
# mismeasure that made diagonal bumpers read ~2×. A per-clip human measurement,
# never auto-fitted.
# values = (diameter_px, confirm_time_s) — the depth tier anchors its trace AT the
# confirmed frame (anchoring elsewhere silently re-scales the ruler).
RIM_PX = {
    "20260605-BN-1": (210, 16.7), "20260605-BN-2": (205, 6.1), "20260605-BN-3": (207, 11.0),
    "20260604-SQ-1": (115, 0.5), "20260604-SQ-3": (122, 0.5),
    "20260609-BN-4": (110, 14.0),
    # 06-16 bench: Rogue DEEP-DISH 45 rim ~570px (the working ruler), vs the blue HUB ~72px
    # the flow seed sits on (a 7x scale error if used). Human-confirmed (Hough median over the
    # set, consistent 565-573 across the 5 clips; the in-app circle-confirm surface). Fixed the
    # absurd 218cm ROM -> ~28cm and made abs velocity ~0.04 RMSE vs Vitruve. (diameter_px, t).
    "20260616-BN-1": (570, 0.3), "20260616-BN-2": (573, 27.3), "20260616-BN-3": (565, 6.0),
    "20260616-BN-4": (570, 9.3), "20260616-BN-5": (570, 24.2),
}

# Working-plate colour per clip (for the colour-mask continuous size trace; the 0605
# travel gym = blue bumpers). Only consulted when the depth tier is active.
PLATE_COLOR = {
    "20260605-BN-1": "blue", "20260605-BN-2": "blue", "20260605-BN-3": "blue",
    "20260605-DL-1": "blue", "20260605-DL-2": "blue", "20260605-DL-3": "blue",
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
                      scale_spec=spec, plausibility_gate=gate, transit_aware=gate)
    reps, meta = VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed, seed_time=seed_time)
    mv = [r["mean_velocity"] for r in reps]
    return (len(reps), (sum(mv) / len(mv) if mv else float("nan")),
            meta["track_confidence"], meta.get("scale_suspect", False),
            meta.get("static_track_suspect", False))


def run_full(clip, tracker, seed, gate=False, rim_px=None, scale=None, band=None):
    """Like run(), but returns the full (reps, meta) so the guardrail can run the no-GT
    track-honesty checks on the actual track behind the count."""
    spec = None
    if scale and tracker != "pose":
        spec = ScaleSpec(top_plate=scale["plate"], kind=scale["kind"], angle=scale["angle"])
    seed_time = None
    if seed is not None and len(seed) == 5:
        seed, seed_time = tuple(seed[:4]), float(seed[4])
    rim_t = None
    if rim_px is not None and isinstance(rim_px, (tuple, list)):
        rim_px, rim_t = float(rim_px[0]), float(rim_px[1])
    cfg = VideoConfig(tracker=tracker, rep_gate="relative", band=band, scale_spec=spec,
                      plausibility_gate=gate, transit_aware=gate, rim_px=rim_px, rim_t=rim_t)
    return VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed, seed_time=seed_time)


def _honesty_of(reps, meta):
    """No-GT track-honesty verdict on the track meta carries (pipeline exposes
    meta['trajectory'] = the chosen track). Returns the honesty dict or None."""
    traj = meta.get("trajectory")
    if traj is None:
        return None
    return _honesty.track_honesty(traj, target_px=meta.get("target_px"), reps=reps)


def _guardrail_board(sets, jitter=False):
    """The generalization guardrail (Track A). For each clip, score BOTH input
    provenances and emit (count Δ vs GT, mean m/s, track-honesty pass/flag):

      * seed-free  — the AUTO path (seed=None, no per-clip input): the BLIND headline.
      * sim-tap    — the registered seed/rim (a real UI surface, but pre-found): the
                     in-sample number, reported separately and labeled.

    Headline = seed-free mean|err| (blind). The blind-vs-in-sample delta quantifies how
    much the human tap/oracle is doing — a big gap is the overfit signal. A count whose
    track FAILS honesty is marked ⚠ (right count, possibly wrong track)."""
    import numpy as _np
    print("\nGENERALIZATION GUARDRAIL (Track A) — provenance-split, no-GT track-honesty\n"
          "  seed-free = BLIND headline (no per-clip input) · sim-tap = registered seed/rim\n")
    hdr = (f"{'set':<16}{'tier':>9}{'GT':>4}  {'prov':<11}{'reps':>7}{'|e|':>4}"
           f"{'mean':>7}  honesty")
    print(hdr); print("-" * len(hdr))
    blind, insample = [], []        # (err, weight)
    for sid in sets:
        clip_rel, trackers, note, band = CLIPS[sid][:4]
        scale = CLIPS[sid][4] if len(CLIPS[sid]) > 4 else None
        try:
            clip = resolve_clip(clip_rel, REPO)
        except Exception as e:
            print(f"{sid:<16}  [clip unavailable: {type(e).__name__}]")
            continue
        refn, _, _, _ = gt_counts(sid)
        gt = _true_gt(sid, refn)
        tier, w = lift_weight(sid)
        rim = RIM_PX.get(sid)
        # seed-free (BLIND): the auto path, zero per-clip input
        try:
            f_reps, f_meta = run_full(clip, "auto", None)
            n = len(f_reps); err = abs(n - gt)
            h = _honesty_of(f_reps, f_meta)
            mv = [r["mean_velocity"] for r in f_reps if not r.get("velocity_relative_only")]
            mean = (sum(mv) / len(mv)) if mv else float("nan")
            hs = ("ok" if (h and h["honest"]) else ("⚠ " + ",".join(h["flags"]) if h else "-"))
            print(f"{sid:<16}{tier:>9}{gt:>4}  {_prov.SEED_FREE:<11}{n:>4}({n-gt:+d}){err:>4}"
                  f"{(f'{mean:.2f}' if mean==mean else '  -'):>7}  {hs}")
            blind.append((err, w))
        except Exception as e:
            print(f"{sid:<16}{tier:>9}{gt:>4}  {_prov.SEED_FREE:<11}  ERR {type(e).__name__}: {e}")
        # sim-tap (IN-SAMPLE): the registered flow seed + rim-confirm, gate on (tap UX)
        seed = trackers.get("flow")
        if seed is not None:
            prov = _prov.provenance(seed=seed, rim_px=rim, band=band, scale=scale)
            try:
                t_reps, t_meta = run_full(clip, "flow", seed, gate=True, rim_px=rim)
                n = len(t_reps); err = abs(n - gt)
                h = _honesty_of(t_reps, t_meta)
                mv = [r["mean_velocity"] for r in t_reps if not r.get("velocity_relative_only")]
                mean = (sum(mv) / len(mv)) if mv else float("nan")
                hs = ("ok" if (h and h["honest"]) else ("⚠ " + ",".join(h["flags"]) if h else "-"))
                jit = ""
                if jitter:
                    perts = [(dx, dy, 0.0) for dx in (-6, 0, 6) for dy in (-6, 0, 6)]
                    sj = _honesty.seed_jitter_stability(
                        lambda dx, dy, dt, s=seed: len(run_full(
                            clip, "flow", _nudge(s, dx, dy), gate=True, rim_px=rim)[0]),
                        perts, base_count=n)
                    jit = f"  jitter={sj['agreement']:.2f}{'' if sj['stable'] else '⚠'}"
                print(f"{'':<16}{'':>9}{'':>4}  {prov:<11}{n:>4}({n-gt:+d}){err:>4}"
                      f"{(f'{mean:.2f}' if mean==mean else '  -'):>7}  {hs}{jit}")
                if _prov.is_blind(prov):    # (shouldn't happen for a seed; guard anyway)
                    blind.append((err, w))
                else:
                    insample.append((err, w))
            except Exception as e:
                print(f"{'':<16}{'':>9}{'':>4}  {prov:<11}  ERR {type(e).__name__}: {e}")
    def _u(p): return _np.mean([e for e, _ in p]) if p else float("nan")
    def _w(p): return (sum(e*w for e, w in p) / sum(w for _, w in p)) if p else float("nan")
    print("\n── HEADLINE (blind = seed-free only) ──")
    print(f"  seed-free  mean|err| = {_u(blind):.2f}   lift-weighted {_w(blind):.2f}   "
          f"(n={len(blind)})   ← the generalization number")
    print(f"  sim-tap    mean|err| = {_u(insample):.2f}   lift-weighted {_w(insample):.2f}   "
          f"(n={len(insample)})   (in-sample; a real UI surface, reported NOT headlined)")
    delta = _u(insample) - _u(blind)
    print(f"  blind−insample delta = {(-delta):+.2f}  "
          f"(how much the human tap closes vs blind; large = blind has headroom)")


def _nudge(seed, dx, dy):
    """Shift a seed bbox by (dx,dy) px, preserving an optional (x,y,w,h,t) time."""
    s = list(seed)
    s[0] += dx; s[1] += dy
    return tuple(s)


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
        clip = resolve_clip(CLIPS[sid][0], REPO)
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
    ap.add_argument("--guardrail", action="store_true",
                    help="Track A generalization guardrail: provenance-split (seed-free "
                         "BLIND headline vs registered sim-tap) + no-GT track-honesty per "
                         "clip + blind-vs-in-sample delta.")
    ap.add_argument("--jitter", action="store_true",
                    help="with --guardrail: also run seed-jitter stability on the sim-tap "
                         "seeds (re-runs the estimator under ±6px nudges — slower).")
    args = ap.parse_args()

    if args.guardrail:
        _guardrail_board([args.only] if args.only else list(CLIPS), jitter=args.jitter)
        return

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
        clip = resolve_clip(clip_rel, REPO)
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
