#!/usr/bin/env python3
"""Build a labeled PLATE-DETECTION dataset from our verified tap-seeded tracks.

The keystone of the CV plate detector: we already have ~26 clips where a HUMAN-CONFIRMED
seed (cv_eval.CLIPS) + a flow track rides the working plate across every frame. That is a
free source of labeled plate boxes — hundreds per clip — without hand-labeling a single
frame. This turns the tap work we already did into detector training data.

Guardrail discipline (Track A) baked in:
  * SPLIT BY CLIP, not by frame. Frames within a clip are near-duplicates; a random-frame
    split leaks and inflates validation. Whole clips are held out (leave-clips-out), the
    same principle as the rest of the guardrail.
  * ONLY emit labels from tracks that pass the no-GT honesty checks (vertical-dominant,
    periodic, moving) — never train the detector on a decoy/body-lock track.
  * Provenance: every label derives from a SIMULATED-TAP seed (a real UI surface). The
    detector learns to reproduce that tap automatically; it is judged blind on held-out
    clips, so it cannot just memorize these seeds.

Output: YOLO-format dataset under dataset/cv_plate/ (images/, labels/, data.yaml) +
a manifest.csv (clip, frame, split, honest). Class 0 = "plate".

    python analysis/scripts/build_plate_dataset.py            # all local clips
    python analysis/scripts/build_plate_dataset.py --step 8   # sample every 8th frame
"""
from __future__ import annotations
import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import VideoConfig, VideoVelocitySource, honesty  # noqa: E402
from vbt_video.frames import PyAVDecoder  # noqa: E402
from vbt_video.track import FlowTracker, track_bidirectional  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402
import cv2  # noqa: E402
import cv_eval  # noqa: E402

REPO = cv_eval.REPO
OUT = os.path.join(REPO, "dataset", "cv_plate")

# Hold these CLIPS out of training entirely (blind validation set) — chosen to span
# lighting/plates/angles (a dark-iron bench, a bumper deadlift, a hex squat) so val
# measures GENERALIZATION, not memorization. Leave-clips-out, never leave-frames-out.
VAL_CLIPS = {"20260609-BN-2", "20260605-DL-2", "20260610-SQ-4"}


def _track_for(sid):
    """Reproduce the verified flow track for a clip from its registered seed (the
    simulated tap). Returns (decoder-frames list lazily via path, track) or None."""
    rel, trackers, *_ = cv_eval.CLIPS[sid]
    seed = trackers.get("flow")
    if seed is None:
        return None
    try:
        clip = resolve_clip(rel, REPO)
    except Exception:
        return None
    src = PyAVDecoder(clip)
    seed_time = None
    if len(seed) == 5:
        seed, seed_time = tuple(seed[:4]), float(seed[4])
    if seed_time is not None:
        track = track_bidirectional(src, seed, seed_time, lambda: FlowTracker())
    else:
        track = FlowTracker().track(src, seed)
    return clip, track


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", type=int, default=6, help="sample every Nth frame")
    ap.add_argument("--only", help="single set_id")
    args = ap.parse_args()

    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    manifest = []
    sets = [args.only] if args.only else list(cv_eval.CLIPS)
    n_lab = {"train": 0, "val": 0}
    for sid in sets:
        out = _track_for(sid)
        if out is None:
            print(f"{sid:<16} skip (no flow seed / unavailable)")
            continue
        clip, track = out
        traj = track.traj
        h = honesty.track_honesty(traj, target_px=track.target_px)
        if not h["honest"]:
            print(f"{sid:<16} SKIP — track not honest {h['flags']} (won't train on a decoy)")
            continue
        split = "val" if sid in VAL_CLIPS else "train"
        # per-frame diameter: prefer the tracker's size samples, else the median target_px
        sizes = track.sizes
        diam = (np.interp(traj[:, 0], sizes[:, 0], sizes[:, 1])
                if sizes is not None and len(sizes) else np.full(len(traj), track.target_px))
        dec = PyAVDecoder(clip)
        for i, f in enumerate(dec):
            if i % args.step or i >= len(traj):
                continue
            H, W = f.img.shape[:2]
            cx, cy = traj[i, 1], traj[i, 2]
            r = max(4.0, diam[i] / 2.0)
            # clip the box to the frame, emit normalized xywh (YOLO)
            x0, y0 = max(0.0, cx - r), max(0.0, cy - r)
            x1, y1 = min(W, cx + r), min(H, cy + r)
            bw, bh = x1 - x0, y1 - y0
            if bw < 4 or bh < 4:
                continue
            ncx, ncy, nw, nh = (x0 + bw / 2) / W, (y0 + bh / 2) / H, bw / W, bh / H
            stem = f"{sid}_{i:05d}"
            cv2.imwrite(os.path.join(OUT, f"images/{split}", stem + ".jpg"), f.img)
            with open(os.path.join(OUT, f"labels/{split}", stem + ".txt"), "w") as fh:
                fh.write(f"0 {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}\n")
            manifest.append((sid, i, split, True))
            n_lab[split] += 1
        print(f"{sid:<16} {split:<5} honest✓  labels so far train={n_lab['train']} val={n_lab['val']}")

    with open(os.path.join(OUT, "data.yaml"), "w") as fh:
        fh.write(f"path: {OUT}\ntrain: images/train\nval: images/val\n"
                 "names:\n  0: plate\n")
    with open(os.path.join(OUT, "manifest.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["set_id", "frame", "split", "honest"])
        w.writerows(manifest)
    print(f"\nDataset: {OUT}  ·  train {n_lab['train']} / val {n_lab['val']} labeled frames  "
          f"·  val clips held out: {sorted(VAL_CLIPS)}")
    print("Train (in a torch/GPU env): yolo detect train data="
          f"{OUT}/data.yaml model=yolo11n.pt epochs=100 imgsz=640")


if __name__ == "__main__":
    main()
