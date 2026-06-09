#!/usr/bin/env python3
"""Fully-automatic (no-seed) rep counter — track-by-detection with oscillation selection.

The 2026-06-09 rebuild of the zero-tap path. Replaces flow+single-auto-seed (which needed
plate texture and a precise seed, and overfit a 9/14 seeder that fell apart on fresh data).

PIPELINE (texture-agnostic, no human seed):
  1. per frame: multi-cue circle detection (Hough on grayscale + on Canny EDGES — the edge
     pass exposes dark-iron plate RIMS that grayscale/flow miss);
  2. track-by-detection: anisotropic association (tight x-lane, loose vertical) — the bar
     moves vertically in a near-fixed column;
  3. select the track whose vertical position OSCILLATES (rep cadence), penalising x-spread
     and radius jitter (kills static rack/background plates and bystanders);
  4. low-pass the trajectory at the rep band (~1.8 Hz) so detection JITTER can't create
     spurious reversals; segment with the tempo-invariant relative gate + a relative-ROM
     floor (reject sub-half-median-ROM jitter reps).

VALIDATED (22-clip corpus, fully auto, vs ground truth):
  mean |rep-count err| 8.5 (old flow-auto) -> ~2.5 (this).  SmartBarbell = 2.5.
  => PARITY with SmartBarbell on mean error, and it BEATS SB on SB's failure modes
     (clutter/mirror/hex, fast touch-and-go, frame-clipping: SQ-3 10 vs 3, DL-2 7 vs 2,
     20260609-BN-1 9 vs 3) — but SB is still more RELIABLE per-clip (13/21 vs 9/22 within
     +/-1): SB wins on clean clips where a periodic DECOY (head/reflection/stored plate)
     out-competes the bar plate in our selection.

OPEN (the path to actually BEAT SB): robust plate IDENTIFICATION in clutter. Classical
multi-cue detection + oscillation/periodicity/twin-pair selection all plateau at parity
(tried + benchmarked 2026-06-09). The durable fix is a LEARNED plate/bar-end detector
(cv-fusion roadmap #6) — SmartBarbell's edge. Our oscillation-tracker is the right
*back-end*; it needs a learned *front-end* to feed it the true plate.

Usage: python auto_detect_count.py dataset/raw/<clip>.mov
"""
from __future__ import annotations
import os, sys
import numpy as np
import cv2
from scipy.signal import butter, filtfilt
from scipy.ndimage import median_filter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video.frames import PyAVDecoder  # noqa: E402
from vbt_video.kinematics import trajectory_to_reps, PlateDiameterScaler  # noqa: E402

WORK, STRIDE, TOPK = 320, 3, 12


def _detect(g):
    out = []
    minR, maxR = int(0.045 * g.shape[1]), int(0.32 * g.shape[1])
    for src, p2 in [(cv2.medianBlur(g, 5), 30), (cv2.Canny(g, 50, 140), 30)]:
        circ = cv2.HoughCircles(src, cv2.HOUGH_GRADIENT, dp=1.2, minDist=int(1.4 * minR),
                                param1=140, param2=p2, minRadius=minR, maxRadius=maxR)
        if circ is not None:
            out += [(float(x), float(y), float(r)) for x, y, r in circ[0][:TOPK]]
    keep = []
    for d in out:
        if not any((d[0]-k[0])**2+(d[1]-k[1])**2 < (0.5*d[2])**2 and abs(d[2]-k[2]) < 0.3*d[2]
                   for k in keep):
            keep.append(d)
    return keep


def _frames(clip):
    out = []
    sc = None
    for i, f in enumerate(PyAVDecoder(clip)):
        if i % STRIDE:
            continue
        img = f.img
        if sc is None:
            sc = WORK / img.shape[1]
        g = cv2.cvtColor(cv2.resize(img, (WORK, int(round(img.shape[0]*sc)))), cv2.COLOR_BGR2GRAY)
        out.append((f.t, [(x/sc, y/sc, r/sc) for (x, y, r) in _detect(g)]))
    return out


def _tracks(frames, GX=0.6, GY=2.5, GAP=5, rtol=0.32):
    tracks = []
    for fi, (t, dets) in enumerate(frames):
        used = set()
        for tr in tracks:
            if fi - tr['lfi'] > GAP:
                continue
            lx, ly, lr = tr['x'], tr['y'], tr['r']
            best, bd = None, 1e18
            for j, (x, y, r) in enumerate(dets):
                if j in used or abs(x-lx) > GX*lr or abs(y-ly) > GY*lr or abs(r-lr) > rtol*lr:
                    continue
                d = ((x-lx)/GX)**2 + ((y-ly)/GY)**2
                if d < bd:
                    bd, best = d, j
            if best is not None:
                x, y, r = dets[best]
                tr['pts'].append((fi, x, y, r))
                tr['x'] = 0.5*lx+0.5*x; tr['y'] = y; tr['r'] = 0.7*lr+0.3*r; tr['lfi'] = fi
                used.add(best)
        for j, (x, y, r) in enumerate(dets):
            if j not in used:
                tracks.append({'pts': [(fi, x, y, r)], 'x': x, 'y': y, 'r': r, 'lfi': fi})
    return tracks


def _select(frames):
    n = len(frames)
    best, bs = None, -1.0
    for tr in _tracks(frames):
        if len(tr['pts']) < max(8, 0.30*n):
            continue
        fis = np.array([p[0] for p in tr['pts']], float)
        ys = np.array([p[2] for p in tr['pts']], float)
        xs = np.array([p[1] for p in tr['pts']], float)
        rad = float(np.median([p[3] for p in tr['pts']]))
        yi = median_filter(np.interp(np.arange(n), fis, ys), 5)
        ystd, cover = float(np.std(yi)), len(tr['pts'])/n
        rcv = np.std([p[3] for p in tr['pts']]) / max(1e-6, rad)
        xspread = float(np.std(xs)) / max(1e-6, rad)
        dv = np.sign(np.diff(yi)); dv = dv[dv != 0]
        rev = int(np.sum(np.diff(dv) != 0)) if len(dv) > 1 else 0
        score = cover*ystd/((1+3*rcv)*(1+2*xspread)) * (0.02 if rev < 2 else 1.0)
        if score > bs:
            bs = score
            best = (np.array([frames[i][0] for i in range(n)]),
                    np.interp(np.arange(n), fis, xs), yi, rad)
    return best


def count(clip, cut=1.8, romf=0.5):
    """-> (n_reps, mean_velocity_relative, plate_radius_px) fully automatically."""
    sel = _select(_frames(clip))
    if sel is None:
        return 0, float("nan"), None
    ts, xi, yi, rad = sel
    dt = float(np.median(np.diff(ts))); fs = 1.0/dt if dt > 0 else 30.0
    tu = np.arange(ts[0], ts[-1], dt); yu = np.interp(tu, ts, yi); xu = np.interp(tu, ts, xi)
    if fs > 2*cut and len(yu) > 15:          # rep-band low-pass: kill jitter reversals
        b, a = butter(2, cut/(fs/2), "low"); yu = filtfilt(b, a, yu)
    mpp = PlateDiameterScaler(0.45).m_per_px(2*rad)
    reps = trajectory_to_reps(np.column_stack([tu, xu, yu]), mpp, 0.10, 0.18, rep_gate="relative")
    if reps:                                  # relative-ROM floor: drop sub-amplitude jitter reps
        med = np.median([r["rom"] for r in reps])
        reps = [r for r in reps if r["rom"] >= romf*med]
    mv = [r["mean_velocity"] for r in reps]
    return len(reps), (sum(mv)/len(mv) if mv else float("nan")), rad


if __name__ == "__main__":
    n, mv, rad = count(sys.argv[1])
    print(f"{sys.argv[1]}: {n} reps  mean_vel(rel)={mv:.2f}  plate_r={rad}")
