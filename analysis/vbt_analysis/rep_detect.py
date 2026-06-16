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
    min_separation_s: float = 0.30,
    drift_cutoff_hz: float = 0.1,
    edge_margin_frac: float = 0.05,
    amp_frac: float = 0.25,
) -> np.ndarray:
    """Return indices of velocity zero-crossings (rep turnarounds).

    Roughly integrate acceleration to velocity, high-pass filter (zero-phase) to
    remove slow integration drift, then take zero-crossings. A single fixed cutoff
    can't win for every tempo: too LOW and a paused/slow set's reps merge with drift
    (06-15 ROW-5 read 6 of 10); too HIGH and noise crossings split clean reps. We
    therefore use a moderately HIGH cutoff (`drift_cutoff_hz`) for sensitivity and
    then **amplitude-gate** the crossings: iteratively drop the crossing bounding the
    weakest segment while that segment's peak |velocity| is under `amp_frac` of the
    median segment amplitude — a real turnaround separates two substantial velocity
    excursions, noise crossings bound tiny ones. This recovers the slow set's reps
    without the high-cutoff over-split (06-15 rows 6/9-of-10 -> 9-10/10). `edge_margin
    _frac` drops filter edge artifacts; `min_separation_s` suppresses chatter.
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
    cr = [int(c) for c in crossings if margin < c < len(t) - margin]

    # Amplitude-gate: a real turnaround sits between two substantial velocity
    # excursions; iteratively remove the crossing next to the weakest segment.
    def seg_amp(lo, hi):
        return float(np.max(np.abs(v_hp[lo:hi + 1]))) if hi > lo else 0.0
    while len(cr) >= 2:
        bounds = [0, *cr, len(t) - 1]
        amps = [seg_amp(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
        pos = [x for x in amps if x > 0]
        med = float(np.median(pos)) if pos else 1.0
        worst = int(np.argmin(amps))
        if amps[worst] >= amp_frac * med:
            break
        del cr[worst if worst < len(cr) else worst - 1]   # drop the inner crossing
    if not cr:
        return np.array([], dtype=int)

    min_gap = max(1, int(min_separation_s * fs))
    kept = [cr[0]]
    for c in cr[1:]:
        if c - kept[-1] >= min_gap:
            kept.append(c)
    return np.array(kept, dtype=int)
