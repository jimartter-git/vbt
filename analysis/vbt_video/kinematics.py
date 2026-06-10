"""Scaling + kinematics — the shared back-end.

Pixels → meters → vertical velocity → per-rep metrics. Unlike the IMU path, video
gives **absolute position** (no integration drift), so velocity is a clean
derivative. We resample to a uniform time base first (phone video is VFR), then
segment concentric reps with the same logic family as the rest of meVBT.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np
from scipy.integrate import cumulative_trapezoid  # noqa: F401  (kept for parity/use)
from scipy.signal import butter, filtfilt, savgol_filter


# ---- Scaler seam: pixels -> meters ----
@dataclass
class PlateDiameterScaler:
    """Scale from a known plate diameter (default 0.45 m standard bumper)."""
    plate_m: float = 0.45

    def m_per_px(self, target_px: float) -> float:
        if target_px <= 0:
            raise ValueError("target_px must be > 0")
        return self.plate_m / target_px


# Body-segment lengths as a fraction of standing height (Drillis & Contini anthropometry).
# Used for the equipment-free pose path: the skeleton *is* the ruler once height is known.
_SEGMENT_HEIGHT_FRAC = {"forearm": 0.146, "upper_arm": 0.186, "hand": 0.108}


@dataclass
class AnthropometricScaler:
    """Scale from a body segment whose real length is known from the user's height —
    the pose path's px→m (no implement in frame). `target_px` is that segment's median
    pixel length (PoseTracker reports the wrist↔elbow forearm by default).

    Absolute scale is only as good as the height prior, BUT velocity *loss* (our headline
    signal) is relative and survives a scale error as long as it's consistent rep-to-rep.
    """
    height_m: float = 1.75
    segment: str = "forearm"

    def m_per_px(self, target_px: float) -> float:
        if target_px <= 0:
            raise ValueError("target_px must be > 0 (pose found no scale segment)")
        frac = _SEGMENT_HEIGHT_FRAC.get(self.segment)
        if frac is None:
            raise ValueError(f"unknown segment '{self.segment}'; have {list(_SEGMENT_HEIGHT_FRAC)}")
        return (self.height_m * frac) / target_px


def _candidate_concentrics(t, v, pos, fs):
    """All positive-velocity runs between velocity sign-changes (the tempo-invariant
    rep turnarounds), with a minimum duration to drop chatter. Returns a list of
    (start, end, peak_velocity, rom_m) — *ungated*; the caller decides what's a rep."""
    b, a = butter(2, min(0.99, 0.1 / (fs / 2)), btype="high")
    vh = filtfilt(b, a, v)
    sign = np.sign(vh); sign[sign == 0] = 1
    crossings = np.where(np.diff(sign) != 0)[0]
    bounds = [0, *crossings.tolist(), len(v) - 1]
    cands = []
    for s, e in zip(bounds[:-1], bounds[1:]):
        if e - s < max(2, int(0.12 * fs)):
            continue
        seg_v = v[s:e + 1]
        if seg_v.mean() <= 0:
            continue
        cands.append((s, e, float(seg_v.max()), float(pos[e] - pos[s])))
    return cands


def _segment_concentric(t, v, pos, peak_min, rom_min, fs, rep_gate="absolute",
                        rel_rom_frac=0.5, rel_peak_frac=0.25,
                        rom_floor=0.04, peak_floor=0.05):
    """Pick which candidate runs are real reps.

    - `rep_gate="absolute"` (default, validated): keep runs clearing fixed
      `rom_min` (real travel, the primary gate) and `peak_min` (a low noise gate
      kept BELOW grind speed so terminal reps survive). Byte-for-byte the v1 rule.
    - `rep_gate="relative"`: tempo-invariant gating. The discriminator is **peak
      velocity relative to the set median**, NOT ROM — because a fast touch-and-go
      or partial-lockout rep has a *small ROM but a normal peak* (you still moved
      the load), whereas jitter has a *low peak*. A fixed ROM gate silently drops
      those partial reps; peak-relative gating keeps them and still rejects jitter
      (which sits an order of magnitude below the set's median peak). A small
      absolute ROM floor removes high-jerk zero-travel spikes. `rel_rom_frac` is
      unused here (kept for signature stability). See docs/sources-and-fusion.md
      "Tempo-invariance".
    """
    cands = _candidate_concentrics(t, v, pos, fs)
    if rep_gate == "absolute":
        return [(s, e) for (s, e, peak, rom) in cands
                if peak >= peak_min and rom >= rom_min]
    if rep_gate != "relative":
        raise ValueError(f"unknown rep_gate '{rep_gate}'; use 'absolute' or 'relative'")
    # Drop pure jitter (high-jerk zero-travel spikes) with a small absolute floor,
    # then gate on PEAK velocity relative to the set median (scale-invariant ratio).
    floored = [(s, e, peak, rom) for (s, e, peak, rom) in cands
               if peak >= peak_floor and rom >= rom_floor]
    if not floored:
        return []
    med_peak = float(np.median([c[2] for c in floored]))
    peak_gate = max(peak_floor, rel_peak_frac * med_peak)
    return [(s, e) for (s, e, peak, rom) in floored if peak >= peak_gate]


def trajectory_to_reps(track_traj, m_per_px, peak_min=0.12, rom_min=0.25,
                       rep_gate="absolute", rom_floor_frac=0.0):
    """`track_traj` = N x 3 (t, cx, cy) px. Returns list of per-rep dicts.
    `rep_gate`: "absolute" (fixed ROM/peak, validated) or "relative" (adaptive,
    tempo-invariant — see `_segment_concentric`)."""
    t = track_traj[:, 0].astype(float)
    y_px = track_traj[:, 2].astype(float)
    # image y grows DOWNWARD → bar up = y decreasing → vertical position (up +):
    pos = (-y_px) * m_per_px

    # de-duplicate / enforce increasing time, then resample to uniform dt (VFR-safe)
    keep = np.concatenate([[True], np.diff(t) > 1e-6])
    t, pos = t[keep], pos[keep]
    if len(t) < 8:
        return []
    dt = float(np.median(np.diff(t)))
    fs = 1.0 / dt
    tu = np.arange(t[0], t[-1], dt)
    posu = np.interp(tu, t, pos)

    win = max(5, int(round(0.10 * fs)) | 1)      # odd window ~100 ms
    win = min(win, (len(posu) // 2) * 2 - 1) if len(posu) > 7 else 5
    if win >= 5 and win < len(posu):
        posu_s = savgol_filter(posu, win, 2)
        vel = savgol_filter(posu, win, 2, deriv=1, delta=dt)
    else:
        posu_s = posu
        vel = np.gradient(posu, dt)

    segs = _segment_concentric(tu, vel, posu_s, peak_min, rom_min, fs, rep_gate)
    out = []
    for i, (s, e) in enumerate(segs, 1):
        seg_v = vel[s:e + 1]
        peak = float(seg_v.max())
        active = np.where(seg_v >= max(0.05, 0.1 * peak))[0]
        a0, a1 = int(active[0]), int(active[-1])
        out.append({
            "rep_index": i,
            "t": round(float(tu[s]), 3),                            # rep start time (s)
            "mean_velocity": round(float(seg_v[a0:a1 + 1].mean()), 3),
            "peak_velocity": round(peak, 3),
            "rom": round(float(posu_s[e] - posu_s[s]) * 100, 1),   # cm
        })
    # Count vs measure: flag reps whose ROM is well under the set median as
    # `partial_rom` so downstream velocity/loss comparisons can exclude them
    # (a partial/no-lockout rep is counted, but isn't apples-to-apples). See
    # docs/sources-and-fusion.md "Tempo-invariance".
    if out:
        med = float(np.median([r["rom"] for r in out]))
        for r in out:
            if med > 0 and r["rom"] < 0.7 * med:
                r["flag"] = "partial_rom"
        # Optional relative-ROM floor: REJECT (don't just flag) reps whose ROM is well below
        # the set median — high-frequency detection jitter (DetectTracker) makes tiny-ROM
        # spurious reps; a real fatigued rep keeps most of its ROM. Scale-invariant. Default
        # 0 = off (flow path unchanged); DetectTracker uses ~0.5.
        if rom_floor_frac > 0 and med > 0:
            out = [r for r in out if r["rom"] >= rom_floor_frac * med]
            for i, r in enumerate(out, 1):
                r["rep_index"] = i
    return out
