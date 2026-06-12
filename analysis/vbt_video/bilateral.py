"""Bilateral (two bar-end) fusion — the first SIGNAL-level fusion tier.

Design: docs/cv-fusion.md "Signal fusion — the tier ABOVE selection". Two verified
tracks of the SAME bar's two plate faces are fused per-primitive:

* **Tilt/whip cancellation** (`mode="avg"`): bar tilt moves the ends in opposite
  directions, so averaging the two centred metric signals cancels it (and halves
  independent tracker jitter). Each end uses its OWN constant ruler (its plate's
  median apparent diameter), so a static depth difference between ends is already
  handled.
* **Depth correction** (`mode="depth"`): the per-end metric height is computed with
  the PER-FRAME ruler,  pos_i(t) = −plate_m · (cy_i(t) − cy0) / d_i(t),  which is
  pinhole-exact and FOCAL-LENGTH-FREE — d/dt of it captures the out-of-plane motion
  that makes diagonal clips read ~2× (the scale varies through the ROM; cv-fusion
  "BN-3-0605 physics"). The cost: diameter noise is amplified by (cy − cy0), so
  d_i(t) is robust-clipped and rep-band low-passed before use. Falls back to "avg"
  per-end when a track has no size trace.
* **Disagreement is information**: the residual between the two centred end signals
  is returned per-frame and summarised per-rep — a free quality flag (bar tilt or a
  mis-tracked end), surfaced, never silently averaged away (guardrail #3).

The fused signal re-enters the standard back-end (`trajectory_to_reps`) unchanged:
identity was already resolved per-end (verified taps) — this layer only repairs
magnitude/shape, per the identity-before-blending guardrail.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, medfilt

from .kinematics import trajectory_to_reps


def _smooth_diameter(sizes, grid_t, lp_cut=1.2):
    """Robust per-frame diameter d(t) on `grid_t` from sparse (t, d) samples:
    clip outliers to ±20% of the median (a mis-fit rim sample must not bend the
    ruler), interpolate, then low-pass WELL below rep frequency's harmonics so
    diameter noise can't masquerade as velocity."""
    s = np.asarray(sizes, dtype=float)
    if s.ndim != 2 or len(s) < 3:
        return None
    med = float(np.median(s[:, 1]))
    d = np.clip(s[:, 1], 0.8 * med, 1.2 * med)
    if len(d) >= 5:
        d = medfilt(d, 5)
    di = np.interp(grid_t, s[:, 0], d)
    dt = float(np.median(np.diff(grid_t)))
    fs = 1.0 / dt if dt > 0 else 30.0
    if fs > 2.5 * lp_cut and len(di) > 18:
        b, a = butter(2, lp_cut / (fs / 2), btype="low")
        di = filtfilt(b, a, di)
    return di


def _end_position(track, plate_m, cy0, grid_t, depth_correct):
    """One end's metric vertical position (up-positive) on the common grid."""
    t, cy = track.traj[:, 0], track.traj[:, 2]
    cyi = np.interp(grid_t, t, cy)
    if depth_correct and getattr(track, "sizes", None) is not None:
        di = _smooth_diameter(track.sizes, grid_t)
        if di is not None and np.all(di > 1):
            # pinhole-exact, focal-length-free: Y_i = (cy_i − cy0)·Z_i/f = (cy_i − cy0)·D/d_i
            return -plate_m * (cyi - cy0) / di
    return -cyi * (plate_m / track.target_px)        # constant per-end ruler (avg tier)


def fuse_bilateral(track1, track2, plate_m, frame_h, mode="avg", cy0=None):
    """Fuse two bar-end tracks → (grid_t, fused_pos_m, disagreement_m).

    `mode`: "avg" (tilt cancellation, constant per-end rulers) or "depth"
    (per-frame rulers; falls back per-end when no size trace). `cy0`: optical-centre
    row; defaults to the frame middle (uncalibrated phone assumption — documented).
    Each end is CENTRED (its own mean removed) before fusing, so per-end origin and
    static depth offsets drop out; only shape/magnitude is fused."""
    t0 = max(track1.traj[0, 0], track2.traj[0, 0])
    t1 = min(track1.traj[-1, 0], track2.traj[-1, 0])
    if t1 - t0 < 1.0:
        raise ValueError("bilateral: tracks share <1 s of timeline")
    dt = float(np.median(np.diff(track1.traj[:, 0])))
    grid_t = np.arange(t0, t1, max(dt, 1e-3))
    if cy0 is None:
        cy0 = frame_h / 2.0
    depth = mode == "depth"
    p1 = _end_position(track1, plate_m, cy0, grid_t, depth)
    p2 = _end_position(track2, plate_m, cy0, grid_t, depth)
    p1c = p1 - p1.mean()
    p2c = p2 - p2.mean()
    fused = (p1c + p2c) / 2.0
    return grid_t, fused, (p1c - p2c)


def bilateral_reps(track1, track2, plate_m, frame_h, mode="avg",
                   plausibility=True, disagree_tol=0.25):
    """Fused per-rep metrics + per-rep L/R disagreement flags.

    Returns (reps, meta). Reps whose rep-window RMS end-disagreement exceeds
    `disagree_tol` × the set's median ROM are flagged `lr_disagree` (kept, never
    dropped — disagreement is a quality signal for the editor, not a verdict)."""
    grid_t, fused, resid = fuse_bilateral(track1, track2, plate_m, frame_h, mode=mode)
    traj = np.column_stack([grid_t, np.zeros_like(fused), -fused])   # back-end expects px-y-down
    reps = trajectory_to_reps(traj, 1.0, rep_gate="relative", plausibility=plausibility)
    med_rom = float(np.median([r["rom"] for r in reps])) / 100.0 if reps else 0.0
    n_dis = 0
    for r in reps:
        i0 = int(np.searchsorted(grid_t, r["t"]))
        i1 = int(np.searchsorted(grid_t, r["t_end"]))
        rms = float(np.sqrt(np.mean(resid[i0:max(i1, i0 + 1)] ** 2)))
        r["lr_rms_m"] = round(rms, 4)
        if med_rom > 0 and rms > disagree_tol * med_rom:
            r["flag"] = "lr_disagree"
            n_dis += 1
    meta = {
        "mode": mode,
        "lr_rms_m": round(float(np.sqrt(np.mean(resid ** 2))), 4),
        "n_lr_disagree": n_dis,
        "confidence": round(min(track1.confidence, track2.confidence), 3),
    }
    return reps, meta
