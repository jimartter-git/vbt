#!/usr/bin/env python3
"""Train + BLIND-evaluate the CV plate detector.

Trains a YOLO detector on the tap-seeded labels (build_plate_dataset.py), then evaluates it
the way that matters: on the HELD-OUT val clips it never trained on (Track A — leave-clips-
out, no leave-frames-out leakage). Reports both the detection metric (mAP, from ultralytics)
and the PRODUCT metric — seed-free rep COUNTS using the learned detector vs ground truth and
vs the classical heuristic auto path.

    # full run in a GPU env:
    python analysis/scripts/train_plate_detector.py --epochs 100 --model yolo11n.pt --imgsz 640
    # CPU smoke test (proves the pipeline end-to-end):
    python analysis/scripts/train_plate_detector.py --epochs 3 --model yolo11n.pt --imgsz 320 --eval-only-val
"""
from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402
import cv_eval  # noqa: E402
from build_plate_dataset import VAL_CLIPS  # noqa: E402

REPO = cv_eval.REPO
DATA = os.path.join(REPO, "dataset", "cv_plate", "data.yaml")


def blind_count_eval(weights):
    """Seed-free rep counts on the HELD-OUT val clips, learned detector vs heuristic auto."""
    print("\nBLIND rep-count eval on held-out val clips (never trained on):")
    print(f"  {'clip':<16}{'GT':>4}{'learned':>9}{'heuristic':>11}")
    for sid in sorted(VAL_CLIPS):
        if sid not in cv_eval.CLIPS:
            continue
        clip = resolve_clip(cv_eval.CLIPS[sid][0], REPO)
        refn, _, _, _ = cv_eval.gt_counts(sid)
        gt = cv_eval._true_gt(sid, refn)
        try:
            lreps, _ = VideoVelocitySource(VideoConfig(
                tracker="learned", learned_model=weights, rep_gate="relative")).estimate(clip)
            lc = f"{len(lreps)}({len(lreps)-gt:+d})"
        except Exception as e:
            lc = f"ERR:{type(e).__name__}"
        try:
            hreps, _ = VideoVelocitySource(VideoConfig(tracker="auto")).estimate(clip)
            hc = f"{len(hreps)}({len(hreps)-gt:+d})"
        except Exception as e:
            hc = f"ERR:{type(e).__name__}"
        print(f"  {sid:<16}{gt:>4}{lc:>9}{hc:>11}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--weights", help="skip training; eval these weights")
    args = ap.parse_args()

    if args.weights:
        weights = args.weights
    else:
        from ultralytics import YOLO
        model = YOLO(args.model)
        res = model.train(data=DATA, epochs=args.epochs, imgsz=args.imgsz,
                          project=os.path.join(REPO, "dataset", "cv_plate", "runs"),
                          name="plate", exist_ok=True, verbose=True)
        weights = os.path.join(res.save_dir, "weights", "best.pt")
        print(f"\ntrained weights: {weights}")
        # ultralytics detection metric on the held-out val clips' frames
        try:
            m = model.val(data=DATA, imgsz=args.imgsz)
            print(f"val mAP50={m.box.map50:.3f}  mAP50-95={m.box.map:.3f}")
        except Exception as e:
            print(f"(val metric skipped: {e})")

    blind_count_eval(weights)


if __name__ == "__main__":
    main()
