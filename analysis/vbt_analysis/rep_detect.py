"""Rep / turnaround detection.

ZUPT needs to know where velocity ~= 0 (rep turnarounds). At a turnaround the
bar momentarily stops, so velocity crosses zero there — but acceleration is
*maximal* (it's reversing), so we can't find turnarounds from "quiet" accel.
Instead we roughly integrate to a (drifty) velocity, de-trend the slow drift,
and take the zero-crossings as turnaround candidates.

This is a deliberately simple PoC detector. Tune / replace once real recordings
expose the failure modes (pauses, false crossings from arm noise, etc.).
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt


def _highpass(v, fs, cut_hz):
    b, a = butter(2, min(0.99, cut_hz / (fs / 2.0)), btype="high")
    return filtfilt(b, a, v)


def _amplitude_gate(cr, v_hp, n, amp_frac):
    """Iteratively drop the crossing bounding the weakest velocity segment: a real
    turnaround separates two substantial excursions; noise crossings bound tiny ones."""
    def seg_amp(lo, hi):
        return float(np.max(np.abs(v_hp[lo:hi + 1]))) if hi > lo else 0.0
    cr = list(cr)
    while len(cr) >= 2:
        bounds = [0, *cr, n - 1]
        amps = [seg_amp(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
        pos = [x for x in amps if x > 0]
        med = float(np.median(pos)) if pos else 1.0
        worst = int(np.argmin(amps))
        if amps[worst] >= amp_frac * med:
            break
        del cr[worst if worst < len(cr) else worst - 1]
    return cr


def detect_turnarounds(
    t: np.ndarray,
    a_vert: np.ndarray,
    min_separation_s: float = 0.30,
    drift_cutoff_hz: float = 0.1,
    edge_margin_frac: float = 0.05,
    amp_frac: float = 0.25,
    decouple: bool = False,
    count_cutoff_hz: float = 0.25,
    anchor_cutoff_hz: float = 0.05,
    snap_window_s: float = 0.30,
) -> np.ndarray:
    """Return indices of velocity turnarounds (rep boundaries) for ZUPT.

    Roughly integrate acceleration to velocity, high-pass to remove slow drift, take
    the zero-crossings, then **amplitude-gate** them (drop crossings bounding tiny
    velocity excursions — noise, not turnarounds).

    **`decouple` (off by default)** addresses a fundamental tension a single cutoff
    can't: COUNTING reps wants a HIGH cutoff (a paused/slow set's reps otherwise merge
    with drift — 06-15 ROW-5), but the integration ANCHORS want it LOW, because an
    aggressive high-pass phase-shifts the crossings INWARD, shrinking the concentric
    window and INFLATING mean velocity (0.25 Hz inflated the synthetic mean
    0.509 -> 0.575). With `decouple=True` we COUNT at `count_cutoff_hz` (high) then
    SNAP each anchor to the nearest |velocity| minimum of a GENTLY drift-removed signal
    (`anchor_cutoff_hz`, low → no phase distortion) within `snap_window_s` — recovering
    sensitivity WITHOUT inflating velocity (synthetic stays 0.52).

    It is **off by default** because on the 06-15 rows it's a net wash: it fixes a
    missed rep (ROW-4 9→10) but over-counts a clean set (ROW-3 10→11) and the binding
    constraint — ROW-5 reading ~1/3 the accel of its peers — is a DEGRADED RECORDING,
    a capture problem no detector can fix. Use `decouple=True` for genuinely
    drift-merged signals where the default under-counts; keep it off for clean sets
    where velocity accuracy is paramount.
    """
    t = np.asarray(t, dtype=float)
    a_vert = np.asarray(a_vert, dtype=float)
    if len(t) < 16:
        return np.array([], dtype=int)

    fs = 1.0 / np.median(np.diff(t))
    v_rough = cumulative_trapezoid(a_vert, t, initial=0.0)
    margin = int(edge_margin_frac * len(t))

    cut = count_cutoff_hz if decouple else drift_cutoff_hz
    v_hp = _highpass(v_rough, fs, cut)
    sign = np.sign(v_hp); sign[sign == 0] = 1
    cr = [int(c) for c in np.where(np.diff(sign) != 0)[0] if margin < c < len(t) - margin]
    cr = _amplitude_gate(cr, v_hp, len(t), amp_frac)
    if not cr:
        return np.array([], dtype=int)

    if decouple:        # snap anchors to the undistorted turnaround positions
        v_gentle = _highpass(v_rough, fs, anchor_cutoff_hz)
        win = max(1, int(snap_window_s * fs))
        cr = sorted({max(0, c - win) + int(np.argmin(np.abs(
            v_gentle[max(0, c - win):min(len(t) - 1, c + win) + 1]))) for c in cr})

    min_gap = max(1, int(min_separation_s * fs))
    kept = []
    for c in cr:
        if not kept or c - kept[-1] >= min_gap:
            kept.append(c)
    return np.array(kept, dtype=int)
