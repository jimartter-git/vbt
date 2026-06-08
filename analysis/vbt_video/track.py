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
    size_cv: float = 0.0      # coeff. of variation of the size samples — a scale-quality
    #   signal (a jittery plate radius = unreliable px→m). 0 = unknown/stable.


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


def _detect_plate(img, x0b, x1b, r0, near=None, minR=None, maxR=None, param2=None):
    """One Hough plate detection in the x-band, nearest to `near` (or band centre).
    Returns (cx, cy, r) or None. Default radius window is ±20% of `r0`; pass absolute
    `minR`/`maxR` for a wide, seed-size-independent search (scale calibration). Vote
    threshold scales with radius unless `param2` is given. Used by FlowTracker for scale."""
    x0b = max(0, int(x0b)); x1b = min(int(x1b), img.shape[1])
    roi = img[:, x0b:x1b]
    g = cv2.medianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 5)
    p2 = param2 if param2 is not None else int(np.clip(0.25 * r0, 18, 42))
    mn = int(minR) if minR is not None else int(0.80 * r0)
    mx = int(maxR) if maxR is not None else int(1.20 * r0)
    circ = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=80, param1=120,
                            param2=p2, minRadius=mn, maxRadius=max(mn + 1, mx))
    if circ is None:
        return None
    cand = [(x0b + float(q[0]), float(q[1]), float(q[2])) for q in circ[0]]
    nx, ny = near if near is not None else ((x0b + x1b) / 2.0, img.shape[0] / 2.0)
    return min(cand, key=lambda q: (q[0] - nx) ** 2 + (q[1] - ny) ** 2)


class FlowTracker(Tracker):
    """Temporal optical-flow tracker — the blur-proof, never-drops-a-rep default.

    The lesson from PlateTracker: a per-frame *detector* has no memory, so motion blur
    (no edge) or a low/occluded grind rep means nothing to detect — we drop reps. A
    commercial tool like SmartBarbell doesn't, because it tracks *temporally*: it follows
    the same patch of **texture** frame-to-frame and coasts through a blurred frame
    because the patch is still locally matchable even when the global shape is gone. It
    also doesn't care *what* the texture is — plate face, logo, collar, bar knurling — so
    it works filmed from in front of or behind the bar, from either side.

    Division of labour (the design that matched the commercial composite on our clip):
      - **Flow owns position.** Pyramidal Lucas-Kanade on a cloud of feature points,
        integrating the *median per-point displacement* each frame (robust to losing
        any subset of points). **Forward-backward error culling** (the MedianFlow trick)
        keeps only points that track cleanly round-trip — this is what kills drift, so
        the cloud holds an entire set without re-seeding.
      - **The detector owns scale only.** It periodically samples the plate diameter
        (`_detect_plate`) for a robust median px→m — but **never** moves the position
        (letting an unreliable detection yank the position re-introduces exactly the
        distractor jumps flow avoids).

    Seed `bbox` localises the plate to seed the point cloud and the scale lane; `band`
    (else seed-derived) bounds the scale detector. Output is the usual `(t, cx, cy)`
    trajectory — scaling/kinematics/segmentation downstream are untouched.

    ROW-ARC OVER-READ (2026-06-01, diagnosed): on a barbell-ROW arc this over-reads
    *vertical* travel ~1.4× (side view 1.17 vs apps 0.63–0.78). NAILED via an on-frame
    overlay + trajectory instrumentation: it is NOT discrete jumps (jerk-limiting removes
    only ~2%; a motion/Kalman prior conserves net displacement and can't fix an amplitude
    bias) and NOT 2D-correctable (RANSAC affine was a no-op). It's a *smooth* migration of
    the face-texture centroid off the plate hub as the plate tilts/occludes against the
    torso at the top of the pull — an out-of-plane effect a flat point cloud can't see, but
    the circular RIM can. MITIGATION: `anchor_alpha` slowly pulls position to the detected
    rim centre (side 1.17→0.86; a no-op on square-on bench, rmse 0.033 preserved). Not yet a
    full closure — residual gap is plate-detector-quality-limited (robust rim fit = next
    step). See docs/generalization.md "Field finding (2026-06-01)".

    OCCLUSION (2026-06-04): when flow loses lock (a hand/rack crosses the plate, the
    bar clips the frame edge for a beat, motion-blur kills the texture), v1 *freezes*
    position — flattening the trajectory and erasing whatever reps happen in that gap.
    Opt-in `occlusion_robust=True` instead (a) **coasts** through a short gap on the
    last good velocity (decaying, so it doesn't run away or overshoot a turnaround) and
    (b) **re-acquires** by re-detecting the plate near the predicted position and
    re-seeding the cloud the instant the target reappears. Default OFF — the validated
    default path is byte-for-byte unchanged; enable it for cluttered/edge-clipping clips.

    SCALE (2026-06-04): px→m comes from the plate diameter, and v1 sizes the plate with a
    Hough search locked to ±20% of the SEED box — so a too-small seed under-sizes the
    plate and inflates velocity AND ROM by the same factor (squats read ~2× high). The
    reliable fix is a well-sized seed. `robust_scale=True` is an EXPERIMENTAL (default-OFF)
    attempt to make size seed-independent via a wide calibration scan (`_calibrate_scale`);
    stress-testing showed no simple circle-selection rule is robust across plate-size ×
    clutter — it either misses the under-sized squat or breaks the device-grade bench/rows.
    The durable fix is a learned plate detector (docs/cv-fusion.md roadmap #6) or a
    user-confirmed plate size. Left in, opt-in, for experimentation on a given clip.
    """
    def __init__(self, band=None, band_lr=(1.18, 1.51), win=41, levels=4,
                 fb_thresh=1.0, min_pts=25, seed_pts=140, scale_every=10,
                 lat_cull=1.4, anchor_alpha=0.0, anchor_every=3,
                 occlusion_robust=False, coast_frames=4, coast_decay=0.8, min_lost=3,
                 robust_scale=False, cal_frames=24, cal_stride=2, cal_lane_frac=0.18,
                 cal_min_r=8, cal_max_frac=0.25, cal_param2=28, cal_min_hits=4):
        self.robust_scale = robust_scale      # EXPERIMENTAL seed-independent scale (default off)
        self.cal_frames = cal_frames          # how many early frames to scan
        self.cal_stride = cal_stride          # scan every Nth frame
        self.cal_lane_frac = cal_lane_frac    # scan lane half-width as a fraction of frame W
        self.cal_min_r = cal_min_r            # absolute min plate radius (px)
        self.cal_max_frac = cal_max_frac      # absolute max plate radius as a fraction of frame H
        self.cal_param2 = cal_param2          # Hough vote threshold for the wide scan
        self.cal_min_hits = cal_min_hits      # min detections before trusting the median
        self.occlusion_robust = occlusion_robust
        self.coast_frames = coast_frames     # max consecutive lost frames to coast through
        self.coast_decay = coast_decay        # per-frame velocity decay while coasting
        self.min_lost = min_lost              # only re-acquire after this many lost frames —
        #   so an isolated dropped frame on a HEALTHY track just coasts (gentle), and we never
        #   snap to a distractor on a clip that doesn't need it (no-op when lock is good)
        self.band = band
        self.band_lr = band_lr
        self.lk = dict(winSize=(win, win), maxLevel=levels,
                       criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
        self.fb_thresh = fb_thresh      # max forward-backward round-trip error (px)
        self.min_pts = min_pts          # re-seed the cloud below this many clean points
        self.seed_pts = seed_pts        # target cloud size
        self.scale_every = scale_every  # detector cadence for scale samples (frames)
        self.lat_cull = lat_cull        # cull points > lat_cull*r from the cloud's x-median
        # Optional position anchor: slowly pull the integrated position toward the plate's
        # RIM-circle centre (the detector), correcting the smooth centroid migration the
        # face-texture cloud accrues as the plate tilts/occludes on a row (diagnosed on the
        # side view). 0 → off (default; flow owns position unchanged). >0 → complementary
        # gain per gated detection; gated near the current estimate so a distractor can't yank.
        self.anchor_alpha = anchor_alpha
        self.anchor_every = anchor_every

    def _seed(self, g, cx, cy, rad):
        mask = np.zeros_like(g)
        cv2.circle(mask, (int(cx), int(cy)), int(1.05 * rad), 255, -1)
        return cv2.goodFeaturesToTrack(g, maxCorners=self.seed_pts, qualityLevel=0.01,
                                       minDistance=8, mask=mask)

    def _calibrate_scale(self, source, cx, cy, r0_hint):
        """Find the true plate radius independent of the seed's size: a WIDE-radius Hough
        scan over a generous lane on early frames. Per frame, take the LARGEST circle whose
        centre is concentric with the seed (the rim encloses the hub; both are centred, so
        'nearest' wrongly grabs the small hub and 'all-pooled' is dragged down by background
        clutter). Median those per-frame rims across frames for robustness. Returns the
        median radius or None if too few hits. The seed gives WHERE; this gives HOW BIG."""
        rims = []
        for j, f in enumerate(source):
            if j >= self.cal_frames:
                break
            if j % self.cal_stride:
                continue
            H, W = f.img.shape[:2]
            half = max(self.band_lr[0] * r0_hint, self.cal_lane_frac * W)
            x0 = max(0, int(cx - half)); x1 = min(W, int(cx + half))
            g = cv2.medianBlur(cv2.cvtColor(f.img[:, x0:x1], cv2.COLOR_BGR2GRAY), 5)
            maxR = min(int(self.cal_max_frac * H), (x1 - x0) // 2)   # can't be wider than the lane
            circ = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=60, param1=120,
                                    param2=self.cal_param2, minRadius=self.cal_min_r,
                                    maxRadius=max(self.cal_min_r + 1, maxR))
            if circ is None:
                continue
            prox = max(0.6 * r0_hint, 0.06 * W)     # rim/hub are concentric with the seed
            near = [q[2] for q in circ[0]
                    if (x0 + q[0] - cx) ** 2 + (q[1] - cy) ** 2 <= prox ** 2]
            if near:
                rims.append(max(near))               # the rim is the largest concentric circle
        if len(rims) >= self.cal_min_hits:
            return float(np.median(rims))
        return None

    def track(self, source: FrameSource, seed_bbox) -> Track:
        x, y, w, h = [float(v) for v in seed_bbox]
        cx, cy = x + w / 2.0, y + h / 2.0
        r0 = (w + h) / 4.0
        # Seed-size-independent scale: re-anchor the plate radius from a wide calibration
        # scan (the seed only localises WHERE the plate is). No-op if the seed is already
        # well-sized — the median lands on the same radius. See class docstring "SCALE".
        if self.robust_scale:
            rcal = self._calibrate_scale(source, cx, cy, r0)
            if rcal is not None:
                r0 = rcal
        rmed = r0
        if self.band is not None:
            x0b, x1b = int(self.band[0]), int(self.band[1])
        else:
            x0b = int(max(0, cx - self.band_lr[0] * r0))
            x1b = int(cx + self.band_lr[1] * r0)

        prev = None
        pts = None
        ts, xs, ys, radii = [], [], [], []
        healthy = 0
        n = 0
        last_v = np.zeros(2)     # last good per-frame displacement (for occlusion coast)
        fails = 0                # consecutive lost-lock frames
        for f in source:
            g = cv2.cvtColor(f.img, cv2.COLOR_BGR2GRAY)
            if prev is None:
                d = _detect_plate(f.img, x0b, x1b, rmed, near=(cx, cy))
                if d is not None and (d[0] - cx) ** 2 + (d[1] - cy) ** 2 < (1.2 * rmed) ** 2:
                    cx, cy, rmed = d[0], d[1], d[2]
                    radii.append(d[2])
                pts = self._seed(g, cx, cy, rmed)
            else:
                if pts is None or pts.shape[0] < 4:
                    pts = self._seed(g, cx, cy, rmed)        # recover an empty/depleted cloud
                ok_flow = pts is not None and pts.shape[0] >= 4
                if ok_flow:
                    npts, st1, _ = cv2.calcOpticalFlowPyrLK(prev, g, pts, None, **self.lk)
                    bpts, st2, _ = cv2.calcOpticalFlowPyrLK(g, prev, npts, None, **self.lk)
                    fb = np.abs(bpts - pts).reshape(-1, 2).max(axis=1)
                    good = (st1[:, 0] == 1) & (st2[:, 0] == 1) & (fb < self.fb_thresh)
                else:
                    good = np.zeros(0, dtype=bool)            # no features to track this frame
                if ok_flow and good.sum() >= 8:
                    dxy = np.median((npts[good] - pts[good]).reshape(-1, 2), axis=0)
                    cx += float(dxy[0]); cy += float(dxy[1])
                    pts = npts[good].reshape(-1, 1, 2)
                    mx = np.median(pts[:, 0, 0])
                    keep = np.abs(pts[:, 0, 0] - mx) < self.lat_cull * rmed
                    if keep.sum() >= 8:
                        pts = pts[keep].reshape(-1, 1, 2)
                    healthy += 1
                    last_v = dxy; fails = 0
                elif self.occlusion_robust:
                    # Lost lock. Predict where the target should be, try to RE-ACQUIRE
                    # via the plate detector near that prediction; else COAST briefly.
                    fails += 1
                    pred = (cx + float(last_v[0]), cy + float(last_v[1]))
                    d = (_detect_plate(f.img, x0b, x1b, rmed, near=pred)
                         if fails >= self.min_lost else None)    # re-acquire only on sustained loss
                    # accept only a detection that's BOTH near the prediction AND the right
                    # size (a reflection/background circle usually fails the radius check)
                    if (d is not None and (d[0] - pred[0]) ** 2 + (d[1] - pred[1]) ** 2 < (1.5 * rmed) ** 2
                            and abs(d[2] - rmed) / max(rmed, 1.0) < 0.40):
                        cx, cy, rmed = d[0], d[1], d[2]      # re-acquired — re-seed the cloud
                        pts = self._seed(g, cx, cy, rmed)
                        radii.append(d[2]); healthy += 1; fails = 0; last_v = np.zeros(2)
                    elif fails <= self.coast_frames:         # bridge a short gap on last velocity
                        cx += float(last_v[0]) * self.coast_decay ** fails
                        cy += float(last_v[1]) * self.coast_decay ** fails
                    # else: sustained loss with no re-acquire → hold (the v1 freeze)
                cadence = self.anchor_every if self.anchor_alpha > 0.0 else self.scale_every
                if (n % cadence) == 0:                           # SCALE sample (+ optional anchor)
                    d = _detect_plate(f.img, x0b, x1b, rmed, near=(cx, cy))
                    if d is not None and (d[0] - cx) ** 2 + (d[1] - cy) ** 2 < (1.2 * rmed) ** 2:
                        radii.append(d[2])
                        # slow position correction toward the rim centre (see __init__).
                        if self.anchor_alpha > 0.0 and abs(d[2] - rmed) / max(rmed, 1.0) < 0.20:
                            cx += self.anchor_alpha * (d[0] - cx)
                            cy += self.anchor_alpha * (d[1] - cy)
                if pts is None or pts.shape[0] < self.min_pts:   # re-seed only on depletion
                    pts = self._seed(g, cx, cy, 0.85 * rmed)
            ts.append(f.t); xs.append(cx); ys.append(cy)
            prev = g
            n += 1
        if n == 0:
            raise ValueError("no frames decoded")
        rmed = float(np.median(radii)) if radii else r0
        size_cv = (float(np.std(radii) / np.mean(radii))
                   if len(radii) >= 3 and np.mean(radii) > 0 else 0.0)
        traj = np.column_stack([np.asarray(ts, float), np.asarray(xs), np.asarray(ys)])
        return Track(traj=traj, target_px=2.0 * rmed,
                     confidence=round(healthy / max(1, n - 1), 3), size_cv=round(size_cv, 3))


# ---- Pose front-end: the equipment-free, universal tracker ----
#
# Same `Tracker` contract as the implement trackers — it emits `(t, cx, cy)` for a chosen
# body landmark (wrist for cable/isolation work; hip/shoulder for bodyweight). Downstream
# (scaling, kinematics, segmentation, fusion) cannot tell it apart from FlowTracker. See
# docs/generalization.md for where this fits (one spine, swappable front-ends).
#
# A pose landmark is a 2-for-1: it's both the thing we *track* and a metric *ruler* (the
# skeleton's segment lengths calibrate px→m from the user's height) — so PoseTracker also
# reports a body-segment length in `target_px`, which AnthropometricScaler turns into m/px.

# MediaPipe Pose landmark indices (the subset we use).
_POSE_IDX = {
    "left_wrist": 15, "right_wrist": 16, "left_elbow": 13, "right_elbow": 14,
    "left_shoulder": 11, "right_shoulder": 12, "left_hip": 23, "right_hip": 24,
}


# Modern MediaPipe (>=~0.10.18) removed the legacy `mp.solutions.pose` API in favour of
# the Tasks API (`mp.tasks.vision.PoseLandmarker` + a downloadable `.task` model). We support
# BOTH: prefer Tasks (works on current releases), fall back to solutions (older installs),
# so the package isn't pinned to an old MediaPipe. The model is fetched + cached on first use.
_POSE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                   "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")


def _pose_model_path() -> str:
    """Cached path to the Tasks pose model; download on first use (needs network once)."""
    import os
    import urllib.request
    cache = os.path.join(os.path.expanduser("~"), ".cache", "vbt")
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, "pose_landmarker_lite.task")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        urllib.request.urlretrieve(_POSE_MODEL_URL, path)
    return path


class _MediaPipePoseProvider:
    """Lazy MediaPipe-backed landmark provider. Heavy + needs a first-run `pip install
    mediapipe` (and a one-time model download for the Tasks API) — so it's imported lazily
    and injected, never imported at module load. Returns, per frame, a dict
    {landmark_name: (x_px, y_px, visibility)}; missing/low-confidence landmarks are absent.

    Auto-selects the MediaPipe API: the modern **Tasks** `PoseLandmarker` if available,
    else the legacy **solutions.pose** — so it runs across MediaPipe versions unchanged.
    """
    def __init__(self, min_visibility: float = 0.5, model_path: str | None = None):
        self.min_visibility = min_visibility
        self.model_path = model_path
        self._impl = None        # "tasks" | "solutions"
        self._tasks = None       # PoseLandmarker (tasks)
        self._pose = None        # Pose (solutions)

    def _ensure(self):
        if self._impl is not None:
            return
        import mediapipe as mp  # lazy: not a hard dep of the package
        # Prefer the Tasks API (the only one on current MediaPipe); fall back to legacy.
        if hasattr(mp, "tasks") and hasattr(mp.tasks, "vision"):
            try:
                from mediapipe.tasks.python.core.base_options import BaseOptions
                from mediapipe.tasks.python.vision import (PoseLandmarker,
                                                           PoseLandmarkerOptions, RunningMode)
                model = self.model_path or _pose_model_path()
                self._tasks = PoseLandmarker.create_from_options(PoseLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model),
                    running_mode=RunningMode.VIDEO,
                    min_pose_detection_confidence=0.5, min_tracking_confidence=0.5))
                self._impl = "tasks"
                self._ts_ms = 0
                return
            except Exception:
                self._tasks = None   # fall through to legacy if Tasks setup/download failed
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
            self._pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1,
                                                enable_segmentation=False,
                                                min_detection_confidence=0.5,
                                                min_tracking_confidence=0.5)
            self._impl = "solutions"
            return
        raise RuntimeError("MediaPipe has neither tasks.vision.PoseLandmarker nor "
                           "solutions.pose — install mediapipe (and allow the one-time "
                           "model download), or inject a custom landmark provider.")

    def __call__(self, img) -> dict:
        self._ensure()
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self._impl == "tasks":
            import mediapipe as mp
            self._ts_ms += 33    # monotonic timestamps for VIDEO mode (cadence-agnostic)
            res = self._tasks.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), self._ts_ms)
            if not res.pose_landmarks:
                return {}
            lm = res.pose_landmarks[0]
            return {name: (lm[idx].x * w, lm[idx].y * h, float(lm[idx].visibility))
                    for name, idx in _POSE_IDX.items()
                    if lm[idx].visibility >= self.min_visibility}
        # legacy solutions.pose
        res = self._pose.process(rgb)
        if not res.pose_landmarks:
            return {}
        lm = res.pose_landmarks.landmark
        out = {}
        for name, idx in _POSE_IDX.items():
            p = lm[idx]
            if p.visibility >= self.min_visibility:
                out[name] = (p.x * w, p.y * h, float(p.visibility))
        return out


class PoseTracker(Tracker):
    """Follow a named body landmark — the universal, equipment-free, seed-free tracker.

    `landmark`: which point to report as the trajectory (e.g. "wrist" → load proxy on a
    cable pushdown; "hip" → bodyweight squat/pull-up). `side` picks left/right (or "auto":
    whichever is more consistently visible). `scale_segment`: the two landmarks whose
    pixel distance is the metric ruler (default wrist↔elbow = forearm); its median length
    is returned in `target_px` for AnthropometricScaler.

    `seed_bbox` is accepted for interface symmetry but **ignored** — pose needs no seed
    (that's the onboarding win). `provider` is injectable so the seam is testable without
    the MediaPipe model; defaults to `_MediaPipePoseProvider`.
    """
    def __init__(self, landmark="wrist", side="auto", scale_segment=("wrist", "elbow"),
                 provider=None):
        self.landmark = landmark
        self.side = side
        self.scale_segment = scale_segment
        self.provider = provider or _MediaPipePoseProvider()

    @staticmethod
    def _pick_side(frames_lms, base, side):
        """Choose left/right for a landmark base name by visibility count (or honour side)."""
        if side in ("left", "right"):
            return f"{side}_{base}"
        lcount = sum(1 for d in frames_lms if f"left_{base}" in d)
        rcount = sum(1 for d in frames_lms if f"right_{base}" in d)
        return f"{'right' if rcount >= lcount else 'left'}_{base}"

    def track(self, source: FrameSource, seed_bbox=None) -> Track:
        ts, lms = [], []
        for f in source:
            ts.append(f.t)
            lms.append(self.provider(f.img))
        n = len(ts)
        if n == 0:
            raise ValueError("no frames decoded")

        side = self.side
        track_name = self._pick_side(lms, self.landmark, side)
        seg_a = self._pick_side(lms, self.scale_segment[0], side)
        seg_b = self._pick_side(lms, self.scale_segment[1], side)

        traj, seg_px, seen = [], [], 0
        last = None
        for t, d in zip(ts, lms):
            if track_name in d:
                x, y, _ = d[track_name]
                last = (x, y)
                seen += 1
            elif last is not None:
                x, y = last                    # hold last known (gap); flagged via confidence
            else:
                x, y = np.nan, np.nan
            traj.append((t, x, y))
            if seg_a in d and seg_b in d:
                ax, ay, _ = d[seg_a]; bx, by, _ = d[seg_b]
                seg_px.append(float(np.hypot(ax - bx, ay - by)))
        traj = np.asarray(traj, dtype=float)
        # fill any leading NaNs (before first detection) so kinematics gets a clean series
        good = ~np.isnan(traj[:, 1])
        if good.any():
            idx = np.arange(n)
            traj[:, 1] = np.interp(idx, idx[good], traj[good, 1])
            traj[:, 2] = np.interp(idx, idx[good], traj[good, 2])
        target_px = float(np.median(seg_px)) if seg_px else 0.0
        return Track(traj=traj, target_px=target_px, confidence=round(seen / n, 3))


def auto_seed_motion(source, work_w: int = 256, stride: int = 2, min_hits: int = 6,
                     min_r_frac: float = 0.04, max_r_frac: float = 0.30, param2: int = 26):
    """Motion-aware auto-seed: pick the circle that MOVES, not the largest static blob.

    The working plate is the one circle that travels vertically rep after rep; rack-stored
    plates, a neighbouring bar, and mirror circles sit still. So: detect circles across the
    clip (downscaled for speed), group them into vertical *lanes* (the bar holds an x-lane
    while y oscillates), and choose the lane whose detections span the most vertical travel.
    Anchor the seed at that lane's EARLIEST detection (near frame 0, where the tracker seeds).

    Returns (x, y, w, h) in original pixels, or None if no clearly-moving circle is found
    (caller falls back to the static `auto_seed_bbox`). This is the heuristic stand-in for
    the learned detector (cv-fusion roadmap #6) — enough to make the zero-tap path sensible.
    """
    grays, sc = [], None
    for i, f in enumerate(source):
        if i % stride:
            continue
        sc = work_w / float(f.img.shape[1])
        small = cv2.resize(f.img, (work_w, max(1, int(round(f.img.shape[0] * sc)))))
        grays.append(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    if sc is None or len(grays) < min_hits:
        return None
    H, W = grays[0].shape
    # Temporal motion map: where did pixels change across the clip? The bar plate sweeps a
    # vertical SWATH; rack-stored/background plates (even stacked vertically) sit still. Summing
    # motion down each column gives a per-x "activity" profile that peaks at the working plate's
    # lane — and is NOT fooled by a vertical stack of static plates (a static column stays dark).
    M = np.zeros((H, W), np.float32)
    for a, b in zip(grays, grays[1:]):
        M += cv2.absdiff(a, b).astype(np.float32)
    minR, maxR = max(6, int(min_r_frac * work_w)), int(max_r_frac * work_w)

    # Candidate plate circles from the EARLY frames (near where the tracker will seed, frame 0).
    early = grays[: max(3, len(grays) // 5)]
    cands = []                                                # (frame_idx, x, y, r) in work px
    for j, g in enumerate(early):
        circ = cv2.HoughCircles(cv2.medianBlur(g, 5), cv2.HOUGH_GRADIENT, dp=1.2,
                                minDist=int(1.4 * minR), param1=120, param2=param2,
                                minRadius=minR, maxRadius=max(minR + 1, maxR))
        if circ is not None:
            for x, y, r in circ[0]:
                cands.append((j, float(x), float(y), float(r)))
    if not cands:
        return None

    # Two physically-meaningful motion signals for "the bar plate", combined by PRODUCT so a
    # candidate must score on BOTH:
    #   • disc   — motion INSIDE the circle: the plate sweeps through its own spot every rep
    #              (high); a static plate sits in dead pixels (low) — even one stacked in the
    #              same column. This is what a column/lane profile alone can't separate.
    #   • column — motion down the circle's x-LANE: the plate's vertical swath is active; a
    #              dead column means a spurious local flicker, not the bar.
    # A static plate in a moving column (high column, dead disc) and a flicker in a quiet column
    # (high disc, dead column) both fail the product; the bar plate is the one high on both.
    col = M.sum(axis=0)
    col = cv2.blur(col.reshape(1, -1), (max(3, int(0.03 * W) | 1), 1)).ravel()

    def disc_motion(x, y, r):
        x0, x1 = max(0, int(x - r)), min(W, int(x + r + 1))
        y0, y1 = max(0, int(y - r)), min(H, int(y + r + 1))
        return float(M[y0:y1, x0:x1].mean()) if (x1 > x0 and y1 > y0) else 0.0

    def col_motion(x, r):
        x0, x1 = max(0, int(x - r)), min(W, int(x + r + 1))
        return float(col[x0:x1].mean()) if x1 > x0 else 0.0

    def score(c):
        return disc_motion(c[1], c[2], c[3]) * col_motion(c[1], c[3])

    best = max(cands, key=score)
    if score(best) <= 1e-6:
        return None
    # Stabilise the seed: aggregate the early detections in the winner's x-lane (Hough is noisy
    # frame to frame). Median radius for a well-sized box; anchor y at the EARLIEST hit (≈ the
    # plate's frame-0 position, where the tracker seeds its cloud).
    lane = [c for c in cands if abs(c[1] - best[1]) < best[3]]
    e0 = min(lane, key=lambda c: c[0])
    x, y = e0[1], e0[2]
    r = float(np.median([c[3] for c in lane]))
    inv = 1.0 / sc                                            # work px → original px
    return (int((x - r) * inv), int((y - r) * inv), int(2 * r * inv), int(2 * r * inv))


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
