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


def detect_turnarounds(
    t: np.ndarray,
    a_vert: np.ndarray,
    min_separation_s: float = 0.25,
    drift_cutoff_hz: float = 0.1,
    edge_margin_frac: float = 0.05,
) -> np.ndarray:
    """Return indices of velocity zero-crossings (rep turnarounds).

    We roughly integrate acceleration to velocity, then high-pass filter
    (zero-phase) to remove slow integration drift before taking zero-crossings.
    A global linear de-trend tilts the signal and shifts the crossings; a
    high-pass at `drift_cutoff_hz` (well below rep frequency) removes drift
    without that bias. `edge_margin_frac` drops filter edge artifacts and
    `min_separation_s` suppresses chattery double-crossings.
    """
    t = np.asarray(t, dtype=float)
    a_vert = np.asarray(a_vert, dtype=float)
    if len(t) < 16:
        return np.array([], dtype=int)

    fs = 1.0 / np.median(np.diff(t))
    v_rough = cumulative_trapezoid(a_vert, t, initial=0.0)

    nyq = fs / 2.0
    wn = min(0.99, drift_cutoff_hz / nyq)
    b, a = butter(2, wn, btype="high")
    v_hp = filtfilt(b, a, v_rough)

    sign = np.sign(v_hp)
    sign[sign == 0] = 1
    crossings = np.where(np.diff(sign) != 0)[0]

    margin = int(edge_margin_frac * len(t))
    crossings = crossings[(crossings > margin) & (crossings < len(t) - margin)]
    if len(crossings) == 0:
        return crossings.astype(int)

    min_gap = max(1, int(min_separation_s * fs))
    kept = [int(crossings[0])]
    for c in crossings[1:]:
        if c - kept[-1] >= min_gap:
            kept.append(int(c))
    return np.array(kept, dtype=int)
