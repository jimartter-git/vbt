"""Tracking — the swappable front-end.

A `Tracker` turns frames into a target trajectory `(t, cx, cy)` in pixels, plus a
median target size (for plate-diameter scaling) and a tracking-confidence. Swap the
implementation — region track (v1), plate detector, pose joint, learned point
tracking — without touching scaling or kinematics.

v1 = OpenCV **CSRT**: an accurate discriminative-correlation-filter tracker seeded
by a bbox around the target (plate face / bar end). It tracks a *region*, not a
circle, so non-round/12-sided plates and off-angle views are fine — exactly where
the plate-circle competitors break.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np

from .frames import FrameSource


@dataclass
class Track:
    traj: np.ndarray          # N x 3  (t, cx, cy) pixels
    target_px: float          # median target size (≈ plate diameter in px)
    confidence: float         # 0..1  (fraction of frames the tracker held lock)


class Tracker(ABC):
    @abstractmethod
    def track(self, source: FrameSource, seed_bbox) -> Track: ...


class CSRTTracker(Tracker):
    """OpenCV CSRT region tracker. `seed_bbox` = (x, y, w, h) around the target in
    the first frame (manual, or from `auto_seed_bbox`)."""
    def track(self, source: FrameSource, seed_bbox) -> Track:
        tr = None
        traj, sizes = [], []
        lost = 0
        n = 0
        for i, f in enumerate(source):
            t = f.t
            if tr is None:
                tr = cv2.TrackerCSRT.create()
                x, y, w, h = [float(v) for v in seed_bbox]
                tr.init(f.img, (int(x), int(y), int(w), int(h)))
            else:
                ok, box = tr.update(f.img)
                if ok:
                    x, y, w, h = box
                else:
                    lost += 1            # keep last box; flag via confidence
            traj.append((t, x + w / 2.0, y + h / 2.0))
            sizes.append((w + h) / 2.0)
            n += 1
        if n == 0:
            raise ValueError("no frames decoded")
        return Track(
            traj=np.asarray(traj, dtype=float),
            target_px=float(np.median(sizes)),
            confidence=round(1.0 - lost / n, 3),
        )


class PlateTracker(Tracker):
    """Global, motion-coherent plate tracker — robust where a frame-by-frame circle
    detector (Metric/WL) and a region tracker (CSRT) both fail: heavy motion blur,
    plate clipping the frame at lockout, and a busy gym background full of *other*
    same-size, same-gray circles.

    Two passes:
      1. **Detect** — Hough circles each frame, restricted to the plate's vertical
         *lane* (an x-band, seeded from the bbox) and to a consistent radius. This
         yields a few candidate centres per frame (often the plate *plus* distractors).
      2. **Choose a path** — a global **min-acceleration** dynamic program picks one
         candidate per frame (skipping blurred frames, ≤ `gap`, by interpolation).
         The bar moves smoothly (low acceleration); hopping onto a background circle
         and back costs a large acceleration spike, so the DP *won't* — even though a
         stationary distractor would look "smooth" to a naive nearest-neighbour tracker.
         This motion-coherence is the discriminator appearance/intensity can't give us
         (plate and rack circles measure the same gray).

    The x-band is an ROI hint (like CSRT's seed): default is derived from the seed
    bbox; pass `band=(x0,x1)` to override. Everything downstream — scaling,
    kinematics, segmentation — is untouched.
    """
    def __init__(self, band=None, band_lr=(1.5, 1.5), wacc=0.5, gap=7, gap_pen=5.0,
                 rtol=0.16, kmax=4, rfrac=(0.80, 1.20), param2=None,
                 hough=dict(dp=1.2, minDist=80, param1=120)):
        self.band = band            # explicit (x0, x1) px, or None → derive from seed
        self.band_lr = band_lr      # (left, right) margins in units of plate radius
        self.wacc = wacc            # weight on squared acceleration (px/frame^2)
        self.gap = gap              # max frames a skip-transition may bridge
        self.gap_pen = gap_pen      # per-skipped-frame penalty (favour real detections)
        self.rtol = rtol            # radius tolerance vs the clip's median plate radius
        self.kmax = kmax            # max candidates kept per frame
        self.rfrac = rfrac          # Hough radius search bounds as fraction of seed R0
        self.param2 = param2        # Hough accumulator vote threshold; None → scale with R0
        self.hough = hough          # (Hough votes grow with circumference, hence with R0)

    def track(self, source: FrameSource, seed_bbox) -> Track:
        x, y, w, h = [float(v) for v in seed_bbox]
        cx0, cy0 = x + w / 2.0, y + h / 2.0
        r0 = (w + h) / 4.0
        if self.band is not None:
            x0b, x1b = int(self.band[0]), int(self.band[1])
        else:
            x0b = int(max(0, cx0 - self.band_lr[0] * r0))
            x1b = int(cx0 + self.band_lr[1] * r0)

        # Hough's accumulator votes grow with a circle's circumference (∝ radius), so a
        # fixed vote threshold that's right for a big plate misses a small one — scale it.
        param2 = self.param2 if self.param2 is not None else int(np.clip(0.25 * r0, 18, 42))

        # ---- Pass 1: per-frame radius-consistent candidate centres in the x-band ----
        ts, dets, allr = [], [], []
        for f in source:
            x1b_eff = min(x1b, f.img.shape[1])
            roi = f.img[:, x0b:x1b_eff]
            g = cv2.medianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 5)
            circ = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT,
                                    minRadius=int(self.rfrac[0] * r0),
                                    maxRadius=int(self.rfrac[1] * r0), param2=param2,
                                    **self.hough)
            ds = [] if circ is None else [(x0b + float(q[0]), float(q[1]), float(q[2]))
                                          for q in circ[0]]
            for (_, _, r) in ds:
                allr.append(r)
            ts.append(f.t)
            dets.append(ds)
        n = len(ts)
        if n == 0:
            raise ValueError("no frames decoded")
        rmed = float(np.median(allr)) if allr else r0

        cand = []
        for ds in dets:
            cs = [np.array((cx, cy)) for (cx, cy, r) in ds
                  if abs(r - rmed) / rmed <= self.rtol]
            cs.sort(key=lambda p: (p[0] - cx0) ** 2)     # prefer the seed's vertical lane
            cand.append(cs[: self.kmax])
        cand[0] = [np.array((cx0, cy0))]                  # pin the start to the known plate

        # ---- Pass 2: bounded second-order (min-acceleration) DP over candidates ----
        INF = float("inf")
        V = [[(INF, None, None) for _ in c] for c in cand]   # (cost, v_in, back=(j,l))
        for k in range(len(cand[0])):
            V[0][k] = (0.0, np.zeros(2), None)
        for i in range(1, n):
            for k, p in enumerate(cand[i]):
                best = (INF, None, None)
                for j in range(max(0, i - self.gap), i):
                    for l, q in enumerate(cand[j]):
                        cj, vj, _ = V[j][l]
                        if cj == INF:
                            continue
                        v_out = (p - q) / (i - j)
                        acc = v_out - vj
                        c = cj + self.wacc * float(acc @ acc) + self.gap_pen * (i - j - 1)
                        if c < best[0]:
                            best = (c, v_out, (j, l))
                V[i][k] = best

        # cheapest reachable terminal node, then backtrack (interpolating bridged gaps)
        ei = n - 1
        while ei > 0 and (not cand[ei] or min(s[0] for s in V[ei]) == INF):
            ei -= 1
        ek = int(np.argmin([s[0] for s in V[ei]]))
        pos = {}
        real = 0
        i, k = ei, ek
        while True:
            pos[i] = cand[i][k]
            real += 1
            back = V[i][k][2]
            if back is None:
                break
            j, l = back
            pj = cand[j][l]
            for m in range(j + 1, i):                     # linear-interp the blur gap
                a = (m - j) / (i - j)
                pos[m] = (1 - a) * pj + a * cand[i][k]
            i, k = j, l

        xs = np.full(n, np.nan)
        ys = np.full(n, np.nan)
        for m, p in pos.items():
            xs[m], ys[m] = p
        idx = np.arange(n)
        good = ~np.isnan(xs)
        xs = np.interp(idx, idx[good], xs[good])          # edge-hold the unbridged ends
        ys = np.interp(idx, idx[good], ys[good])

        traj = np.column_stack([np.asarray(ts, float), xs, ys])
        return Track(traj=traj, target_px=2.0 * rmed, confidence=round(real / n, 3))


def auto_seed_bbox(img, min_area_frac: float = 0.004) -> tuple:
    """Best-effort seed: the largest solid blob in the frame (the plate end).

    Contour-based (not Hough) so it tolerates non-round plates. Returns (x,y,w,h).
    This only has to be *good enough to start tracking* — the region tracker
    refines from there. For production this is replaced by a learned detector.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise ValueError("auto_seed_bbox found no contours — pass an explicit --seed")
    H, W = gray.shape
    min_area = min_area_frac * H * W
    best = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(best) < min_area:
        raise ValueError("auto_seed_bbox: largest blob too small — pass --seed")
    x, y, w, h = cv2.boundingRect(best)
    return (x, y, w, h)
