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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS_CSV = os.path.join(REPO, "dataset", "rep_metrics.csv")

# set_id -> (clip path rel to repo, {tracker: seed_bbox or None}, note, band=(x0,x1) or None)
# EVERY registered clip with a ground-truth count lives here — the complete board.
CLIPS = {
    # --- device-grade / good clips (regression guards: must stay at GT) ---
    "20260528-IB-1": ("dataset/raw/20260528-IB-1.mp4",
                      {"flow": (323, 163, 316, 316)},
                      "incline bench 185lb - DEVICE-GRADE (rmse 0.033 vs Stance)", (295, 720)),
    "20260601-ROW-1": ("dataset/raw/20260601-ROW-1.mp4",
                       {"flow": (200, 690, 270, 270)}, "barbell row, side (good clip)", None),
    "20260601-ROW-2": ("dataset/raw/20260601-ROW-2.mp4",
                       {"flow": (300, 660, 260, 250)}, "barbell row, angle (good clip)", None),
    "20260601-ROW-3": ("dataset/raw/20260601-ROW-3.mp4",
                       {"flow": (415, 615, 120, 150)}, "barbell row, front (good clip)", None),
    # --- hard clips ---
    "20260604-SQ-1": ("dataset/raw/20260604-SQ-1.mov",
                      {"flow": (210, 85, 55, 65)}, "squat set1, mirror/rack, low-res", None),
    "20260604-SQ-3": ("dataset/raw/20260604-SQ-3.mov",
                      {"flow": (190, 95, 60, 70)}, "squat set3, fast TnG (adversarial)", None),
    "20260602-SC-1": ("dataset/raw/20260602-SC-1.mov",
                      {"flow": (110, 115, 55, 55), "pose": None},
                      "DB press, hex DB end, side-on (flow on DB end >> pose)", None),
    # NOTE: dataset/raw/20260529-DL-pending.mp4 (a deadlift) is registered but NOT in the
    # board yet — its set mapping (DL-1 vs DL-3) and a seed are unconfirmed. Add once mapped.
}


# Reference trust order: Vitruve (ground truth) > on-bar BLE apps. The highest-priority
# vendor present is the GT reference; the next is shown as the competitor to beat.
_REF_PRIORITY = ["vitruve", "stance", "smartbarbell", "metric"]


def gt_counts(set_id):
    """(ref_count, ref_mean, competitor_label, competitor_count) from the DB — falls back
    to the best on-bar app when there's no Vitruve row (e.g. the row clips)."""
    rows = [r for r in csv.DictReader(open(REPS_CSV))
            if r["set_id"] == set_id and r["metric"] == "mean_velocity"]
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


def run(clip, tracker, seed, adaptive, occlusion=False, band=None):
    cfg = VideoConfig(tracker=tracker, rep_gate=("relative" if adaptive else "absolute"),
                      occlusion_robust=(occlusion and tracker == "flow"), band=band)
    reps, meta = VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed)
    mv = [r["mean_velocity"] for r in reps]
    return (len(reps), (sum(mv) / len(mv) if mv else float("nan")),
            meta["track_confidence"], meta.get("scale_suspect", False))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", dest="only")
    ap.add_argument("--adaptive", action="store_true", help="relative (adaptive) rep gating")
    ap.add_argument("--occlusion", action="store_true", help="flow coast + re-acquire")
    args = ap.parse_args()

    sets = [args.only] if args.only else list(CLIPS)
    print(f"\nCV scoreboard{' [adaptive gate]' if args.adaptive else ''} "
          f"— rep count (Δ vs Vitruve) · mean m/s · track-conf\n")
    hdr = f"{'set':<16}{'GT':>4}{'comp':>14}{'tracker':>9}{'reps':>8}{'mean':>7}{'conf':>7}  note"
    print(hdr); print("-" * len(hdr))
    for sid in sets:
        clip_rel, trackers, note, band = CLIPS[sid]
        clip = os.path.join(REPO, clip_rel)
        gtn, gtmean, comp, compn = gt_counts(sid)
        compstr = f"{comp[:5]}={compn}" if comp else "-"
        first = True
        for tracker, seed in trackers.items():
            try:
                n, mean, conf, suspect = run(clip, tracker, seed, args.adaptive,
                                             args.occlusion, band)
                delta = f"{n}({n - gtn:+d})"
                meanstr = (f"{mean:.2f}?" if suspect else f"{mean:.2f}")   # ? = scale flagged
            except Exception as e:
                delta, meanstr, conf = f"ERR", "-", 0.0
                note = note + f" [{type(e).__name__}: {e}]"
            lead = f"{sid:<16}{gtn:>4}{compstr:>14}" if first else " " * 34
            print(f"{lead}{tracker:>9}{delta:>8}{meanstr:>7}{conf:>7.2f}  {note if first else ''}")
            first = False


if __name__ == "__main__":
    main()
