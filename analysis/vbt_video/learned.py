"""Learned plate localization — the CV detector, behind the SAME seams as everything else.

The seed-free heuristic (`seed_candidates`: HoughCircles × motion) fails on dark iron
(ROW-2 reads 5/10 blind). A learned detector trained on our verified tap-seeded tracks
(`scripts/build_plate_dataset.py`) localizes the working plate where Hough can't. It plugs
in two ways, reusing all the proven machinery:

  * `LearnedPlateTracker` — a track-by-detection front-end (tracker="learned"); the same
    kinematics turn its trajectory into reps, and the Track A honesty checks gate it.
  * `learned_seed_candidates` — a drop-in for `seed_candidates` in the AUTO path, so the
    learned detector proposes the bar plate and the proven flow-verification + honesty gate
    pick/verify it. (Minimal-risk: the detector improves LOCALIZATION; flow still owns the
    smooth velocity trajectory.)

ultralytics/torch are imported LAZILY (optional `requirements-ml.txt`) so the classical
pipeline never needs them. A learner is judged on the SAME blind guardrail as a heuristic.
"""
from __future__ import annotations

import numpy as np

from .track import Track, Tracker


def _load_model(model_path):
    """Lazy YOLO load (keeps torch out of the base import path)."""
    from ultralytics import YOLO
    return YOLO(model_path)


def _detect_frames(src, model, conf=0.25, stride=1, max_frames=None):
    """Run the detector over frames. Returns (times, [per-frame list of (cx,cy,d,conf)])."""
    times, dets = [], []
    for i, f in enumerate(src):
        if stride > 1 and i % stride:
            continue
        if max_frames and len(times) >= max_frames:
            break
        res = model.predict(f.img, conf=conf, verbose=False)[0]
        boxes = []
        for b in res.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            boxes.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0,
                          ((x2 - x1) + (y2 - y1)) / 2.0, float(b.conf[0])))
        times.append(f.t); dets.append(boxes)
    return np.asarray(times, float), dets


class LearnedPlateTracker(Tracker):
    """Track-by-detection using the learned plate model. Associates detections across
    frames by nearest-neighbour to the running centre (seeded by the highest-confidence
    early detection, or `seed_bbox` if given), coasting through misses. Emits the same
    `Track` (traj, target_px, confidence, sizes) as every other front-end."""

    def __init__(self, model_path, conf=0.25, gate_frac=0.5):
        self.model = _load_model(model_path)
        self.conf = conf
        self.gate_frac = gate_frac           # association gate = gate_frac × plate diameter

    def track(self, source, seed_bbox=None):
        times, dets = _detect_frames(source, self.model, conf=self.conf)
        n = len(times)
        if n == 0:
            return Track(traj=np.zeros((0, 3)), target_px=0.0, confidence=0.0)
        # seed the centre: the user tap if given, else the most confident early detection
        if seed_bbox is not None:
            x, y, w, h = seed_bbox
            cx, cy, diam = x + w / 2.0, y + h / 2.0, (w + h) / 2.0
        else:
            cx = cy = diam = None
            for boxes in dets[:max(1, n // 5)]:
                if boxes:
                    bx, by, bd, _ = max(boxes, key=lambda b: b[3])
                    cx, cy, diam = bx, by, bd
                    break
            if cx is None:
                return Track(traj=np.zeros((0, 3)), target_px=0.0, confidence=0.0)
        traj, sizes, hits = [], [], 0
        for t, boxes in zip(times, dets):
            gate = self.gate_frac * (diam or 1.0)
            cand = [b for b in boxes if np.hypot(b[0] - cx, b[1] - cy) <= max(gate, 1.0)]
            if cand:
                bx, by, bd, _ = min(cand, key=lambda b: np.hypot(b[0] - cx, b[1] - cy))
                cx, cy, diam = bx, by, bd
                hits += 1
                sizes.append((t, bd))
            traj.append((t, cx, cy))               # coast (hold last) on a miss
        sizes_arr = np.asarray(sizes, float) if sizes else None
        target_px = float(np.median([s[1] for s in sizes])) if sizes else (diam or 0.0)
        return Track(traj=np.asarray(traj, float), target_px=target_px,
                     confidence=round(hits / n, 3), sizes=sizes_arr)


def learned_seed_candidates(source, model_path, topk=5, conf=0.25, stride=2):
    """Drop-in for `track.seed_candidates`: propose plate seed-bboxes from the learned
    detector, ranked by how much each cluster MOVES (the working plate travels; rack/mirror
    decoys don't). Returns up to `topk` (x,y,w,h) boxes for the auto path to flow-verify."""
    model = _load_model(model_path)
    times, dets = _detect_frames(source, model, conf=conf, stride=stride)
    pts = [(b[0], b[1], b[2]) for boxes in dets for b in boxes]
    if not pts:
        return []
    pts = np.asarray(pts, float)
    # cluster detections by spatial bin; score a cluster by its centre's MOTION span
    diam = float(np.median(pts[:, 2]))
    binsz = max(8.0, diam)
    clusters = {}
    for boxes in dets:
        for bx, by, bd, _ in boxes:
            key = (round(bx / binsz), round(by / binsz))
            clusters.setdefault(key, []).append((bx, by, bd))
    scored = []
    for key, members in clusters.items():
        m = np.asarray(members, float)
        motion = float(np.hypot(np.ptp(m[:, 0]), np.ptp(m[:, 1])))
        cx, cy, d = m[:, 0].mean(), m[:, 1].mean(), m[:, 2].mean()
        scored.append((motion * len(m), cx, cy, d))
    scored.sort(reverse=True)
    out = []
    for _, cx, cy, d in scored[:topk]:
        r = d / 2.0
        out.append((int(cx - r), int(cy - r), int(2 * r), int(2 * r)))
    return out
