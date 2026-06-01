#!/usr/bin/env python3
"""First-pass multi-method CV fusion → a single meVBT velocity per set.

Combines our two independent video estimators into one number + a fusion
confidence, then compares to the commercial apps. Consensus rule (graceful
degradation, per docs/sources-and-fusion.md — NOT a tuned blend):

  * The WRIST (pose) is the independent, direct load-point measurement. We use it
    as the spine ONLY when it passes a cross-method plausibility check — its rep
    count must agree with the flow tracker's (a method's *self-reported* confidence
    is not trustworthy: side-on, MediaPipe "sees" a wrist 92% of frames yet tracks
    it wrong, inventing 20 reps for a 10-rep set). Cross-method disagreement is the
    honest signal; self-confidence is not.
  * The flow+anthro path (plate position, body-segment scale) is an independent
    corroborator: agreement with pose → HIGH confidence; disagreement → MEDIUM
    (we still trust the direct wrist read, but flag the conflict).
  * When pose is implausible (rep count far from flow's — e.g. a pure side view) we
    fall back to flow position with plate-diameter scale, flagged LOW: no
    trustworthy source, and flow over-reads on row arcs (FlowTracker OPEN ISSUE).
    The fusion *reports* low confidence rather than a confident wrong number.
"""
from __future__ import annotations
import argparse
import csv
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS_CSV = os.path.join(REPO, "dataset", "rep_metrics.csv")

POSE_VIS = 0.60         # soft floor on pose visibility (a method must at least see the wrist)
REPCOUNT_TOL = 2        # max |pose reps - flow reps| for pose to be plausible (cross-method check)
AGREE_TOL = 0.15        # rel. agreement (pose vs flow-anthro) for HIGH vs MEDIUM


def _mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def _run(clip, tracker, scale, height, seed):
    cfg = VideoConfig(tracker=tracker, scale=scale, height_m=height)
    reps, meta = VideoVelocitySource(cfg).estimate(clip, seed_bbox=seed)
    return [r["mean_velocity"] for r in reps], meta


def fuse(clip, seed, height):
    pose_v, pose_m = _run(clip, "pose", "implement", height, None)
    fp_v, fp_m = _run(clip, "flow", "implement", height, seed)
    fa_v, fa_m = _run(clip, "flow", "anthro", height, seed)
    pose_conf = pose_m["track_confidence"]
    methods = {
        "pose":        (_mean(pose_v), pose_conf, len(pose_v)),
        "flow+plate":  (_mean(fp_v), fp_m["track_confidence"], len(fp_v)),
        "flow+anthro": (_mean(fa_v), fa_m.get("scale_confidence", 0.0), len(fa_v)),
    }
    # Cross-method plausibility: the wrist is the spine only if it both sees the
    # landmark AND agrees with the flow tracker on HOW MANY reps happened. A wild
    # rep-count mismatch (side-on: pose 20 vs flow 10) means pose is tracking the
    # wrong point regardless of its visibility score → don't trust it.
    pose_plausible = (pose_conf >= POSE_VIS
                      and abs(len(pose_v) - len(fp_v)) <= REPCOUNT_TOL)
    if pose_plausible:
        spine, fused = "pose", pose_v
        agree = abs(_mean(pose_v) - _mean(fa_v)) / _mean(pose_v)
        conf = "HIGH" if agree < AGREE_TOL else "MEDIUM"
    else:
        spine, fused, conf = "flow+plate (fallback)", fp_v, "LOW"
    return {"mevbt": _mean(fused), "conf": conf, "spine": spine,
            "n_reps": len(fused), "methods": methods}


def app_mean(set_id, vendor):
    vals = []
    with open(REPS_CSV) as f:
        for row in csv.DictReader(f):
            if (row["set_id"] == set_id and row["vendor"] == vendor
                    and row["metric"] == "mean_velocity" and (row["flag"] or "") != "phantom"):
                vals.append(float(row["value"]))
    return _mean(vals)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--height-m", type=float, default=1.892)
    p.parse_args()
    h = 1.892
    clips = [
        ("20260601-ROW-1", "side",  "dataset/raw/060126_pendlay1_side.mp4",  (200, 690, 270, 270)),
        ("20260601-ROW-2", "angle", "dataset/raw/060126_pendlay2_angle.mp4", (300, 660, 260, 250)),
        ("20260601-ROW-3", "front", "dataset/raw/060126_pendlay3_front.mp4", (415, 615, 120, 150)),
    ]
    print(f"\nmeVBT (fused CV) vs commercial apps — mean concentric velocity (m/s), height {h} m\n")
    print(f"{'set / view':<22}{'Stance':>8}{'SmartB':>8}{'meVBT':>8}  {'conf':<7}{'spine':<22}")
    print("-" * 84)
    rows = []
    for set_id, view, clip, seed in clips:
        r = fuse(os.path.join(REPO, clip), seed, h)
        st, sb = app_mean(set_id, "stance"), app_mean(set_id, "smartbarbell")
        rows.append((set_id, view, st, sb, r))
        print(f"{set_id+' ('+view+')':<22}{st:>8.2f}{sb:>8.2f}{r['mevbt']:>8.2f}  "
              f"{r['conf']:<7}{r['spine']:<22}")
    print("\nper-method detail (mean m/s · confidence · n_reps):")
    for set_id, view, st, sb, r in rows:
        print(f"  {view:<6} " + " | ".join(
            f"{m}={v[0]:.2f}/{v[1]:.2f}/{v[2]}" for m, v in r["methods"].items()))


if __name__ == "__main__":
    main()
