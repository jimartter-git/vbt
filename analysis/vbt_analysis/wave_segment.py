"""One lift-agnostic, position-domain rep segmenter (Track B).

Replaces the velocity-zero-crossing + three per-lift threshold regimes
(`rep_detect.detect_turnarounds` + `velocity.gate_reps` + the bench/RDL inline
overrides) with a SINGLE config that reads the vertical-displacement WAVE and picks
reps by STRUCTURE — the anti-overfitting fix (CLAUDE.md learning #26, §1b).

The idea (generalizing learning #25's bench position-cycle detector across lifts):
a set is a quasi-periodic wave between two recurring levels — a TOP (lockout /
standing) and a BOTTOM (chest / depth / floor). Every barbell lift here has its
CONCENTRIC = the UPWARD excursion (press up, row up, stand up, RDL lockout, pull up),
so a rep = one bottom→top up-excursion. We identify them structurally:

  * **modal excursion** — the set's own typical bottom→top amplitude (robust median);
    reps are excursions near it, repositions are sub-modal wiggles (rejected by
    prominence, no threshold on m or m/s);
  * **alternating extrema** — bottoms and tops alternate; a one-time unrack or a
    terminal putdown is a non-repeating / unpaired excursion at an END, removed
    structurally (not by a per-lift ROM/MV gate);
  * **cadence** — a minimum inter-rep spacing rejects double-counted sub-rep humps.

Drift control is principled, not a magic cutoff: a gentle high-pass only BOOTSTRAPS
the wave to locate turnarounds, then the shipped per-rep velocity is integrated with
ZUPT anchored AT those turnarounds (zero velocity at each top/bottom) — the classical
two-sided zero-velocity constraint, the same one the rest of meVBT uses.

ONE parameter set for row/bench/squat/RDL. Per-lift VELOCITY calibration (e.g. the RDL
wrist-vs-bar offset) is a SEPARATE, legitimate concern surfaced downstream — this
module only segments and reports the raw integrated velocity + a confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter

from .velocity import integrate_with_zupt

# --- the single, lift-agnostic configuration --------------------------------
# Prominence as a fraction of the set's OWN displacement range (scale-free, so it
# transfers across lifts and people); a rep excursion is a large fraction of the
# range, a reposition wiggle is a small one. Cadence is a MINIMUM gap (reps are
# >~1 s apart on every lift here), so it never merges true reps — it only stops a
# sub-rep hump from double-counting. Amplitude floor rejects an unrack/putdown that
# is far from the set's modal excursion.
DEFAULT_PROMINENCE_FRAC = 0.25
DEFAULT_MIN_CADENCE_S = 0.8
DEFAULT_AMP_FLOOR_FRAC = 0.5      # reject excursions < this × the modal excursion
_BOOTSTRAP_DRIFT_HZ = 0.1         # gentle high-pass to find the wave (NOT for velocity)
_ANCHOR_DRIFT_HZ = 0.05
# Terminal-anomaly strip (the unrack/rerack/putdown family — structural, ENDS only).
# A setup bobble or a terminal putdown betrays itself as a SUB-MODAL upward excursion
# at an END (the lifter doesn't complete the lift — e.g. the RDL putdown descends fully
# but only half-rises before the bar is set down). It is a fraction of the set's OWN
# modal amplitude (scale/lift-free), applied trailing/leading only and stopping at the
# first in-band rep — the same terminal-only philosophy as the CV plausibility/transit
# gates (kinematics.py).
#
# An EARLIER design also stripped on an anomalous time gap (a rerack happens after a
# pause). Rejected after measurement: a real paused rep (SQ-1: a full-amplitude rep
# after an 8 s breath) and a rerack are INDISTINGUISHABLE by gap, amplitude, bottom
# position, AND eccentric depth — every structural feature matches. The gap rule traded
# one main-lift miss for another (dropped SQ-1's real rep to catch SQ-3's extra), a net
# wash that violated "never drop a full-ROM main-lift rep" (learning #15). So we keep
# only the amplitude rule and accept SQ-3's structurally-real-looking extra excursion as
# an honest limit, rather than overfit a gap threshold to ground truth.
_TERMINAL_AMP_FRAC = 0.75         # end excursion < this × modal amplitude → anomalous


@dataclass
class WaveRep:
    rep_index: int
    bottom_idx: int
    top_idx: int
    start_time: float
    end_time: float
    rom: float                      # m, bottom→top displacement (wave amplitude)
    mean_concentric_velocity: float  # m/s (ZUPT-anchored)
    peak_concentric_velocity: float  # m/s


@dataclass
class WaveResult:
    reps: list = field(default_factory=list)
    displacement: np.ndarray = None   # the smoothed wave (m, up-positive)
    velocity: np.ndarray = None       # ZUPT-anchored velocity (m/s)
    anchors: np.ndarray = None        # turnaround indices used for ZUPT
    fs: float = 0.0

    @property
    def count(self) -> int:
        return len(self.reps)


def _bootstrap_displacement(t, a, fs):
    """Doubly-integrate accel→displacement with a gentle high-pass at each stage to
    suppress integration drift, then smooth. This wave is used ONLY to LOCATE the
    turnarounds; the per-rep velocity is re-derived with ZUPT (below)."""
    v = cumulative_trapezoid(a, t, initial=0.0)
    b, al = butter(2, min(0.99, _BOOTSTRAP_DRIFT_HZ / (fs / 2.0)), "high")
    vhp = filtfilt(b, al, v)
    pos = cumulative_trapezoid(vhp, t, initial=0.0)
    b2, al2 = butter(2, min(0.99, _ANCHOR_DRIFT_HZ / (fs / 2.0)), "high")
    posh = filtfilt(b2, al2, pos)
    win = max(5, int(fs * 0.3) | 1)
    win = min(win, (len(posh) // 2) * 2 - 1) if len(posh) > 7 else 5
    if 5 <= win < len(posh):
        posh = savgol_filter(posh, win, 2)
    return posh


def _strip_terminal_anomalies(pairs, pos):
    """Remove unrack/putdown pseudo-reps from the ENDS, structurally.

    A genuine rep matches the set's modal UP-excursion amplitude; a setup bobble or a
    terminal putdown is sub-modal (the lift isn't completed). Strip trailing then
    leading while the end excursion is sub-modal, stopping at the first in-band rep
    (mid-set reps untouched). Needs ≥4 candidates to trust the modal statistic."""
    if len(pairs) < 4:
        return pairs
    amps = np.array([pos[ti] - pos[bi] for bi, ti in pairs])
    modal_amp = float(np.median(amps))
    if modal_amp <= 0:
        return pairs

    def sub_modal(i):
        return amps[i] < _TERMINAL_AMP_FRAC * modal_amp

    lo, hi = 0, len(pairs)
    while hi - lo > 3 and sub_modal(hi - 1):
        hi -= 1
    while hi - lo > 3 and sub_modal(lo):
        lo += 1
    return pairs[lo:hi]


def reps_from_wave(pos, fs, prominence_frac=DEFAULT_PROMINENCE_FRAC,
                   min_cadence_s=DEFAULT_MIN_CADENCE_S,
                   amp_floor_frac=DEFAULT_AMP_FLOOR_FRAC, strip_terminal=True):
    """Read rep up-excursions [(bottom_idx, top_idx), …] straight off a vertical
    DISPLACEMENT wave `pos` (m, up-positive). The structural core, independent of how
    `pos` was obtained — so it can be unit-tested on a clean wave without the
    integration round-trip."""
    pos = np.asarray(pos, dtype=float)
    rng = float(np.percentile(pos, 95) - np.percentile(pos, 5))
    if rng <= 0:
        return []
    dist = max(1, int(fs * min_cadence_s))
    prom = prominence_frac * rng
    mins, _ = find_peaks(-pos, distance=dist, prominence=prom)
    maxs, _ = find_peaks(pos, distance=dist, prominence=prom)
    if len(mins) == 0 or len(maxs) == 0:
        return []
    # Walk the extrema as an ALTERNATING bottom/top sequence (a real wave alternates).
    # Where find_peaks emits two same-type extrema in a row (a shallow intervening
    # turnaround below prominence), keep the more extreme one — so each top is consumed
    # by exactly one bottom (no double-counting a bottom pair onto a shared top).
    events = sorted([(int(i), "min") for i in mins] + [(int(i), "max") for i in maxs])
    walk = []
    for idx, typ in events:
        if walk and walk[-1][1] == typ:
            prev = walk[-1][0]
            more_extreme = pos[idx] < pos[prev] if typ == "min" else pos[idx] > pos[prev]
            if more_extreme:
                walk[-1] = (idx, typ)
        else:
            walk.append((idx, typ))
    # Pair each bottom with the immediately following top → an upward (concentric) excursion.
    pairs = []
    for k in range(len(walk) - 1):
        if walk[k][1] == "min" and walk[k + 1][1] == "max":
            bi, ti = walk[k][0], walk[k + 1][0]
            if ti - bi >= int(fs * 0.2):     # too brief to be a real concentric
                pairs.append((bi, ti))
    if not pairs:
        return []
    # Structural rejection: keep excursions near the set's MODAL amplitude; an unrack
    # bobble / terminal putdown is far below it (and at an end). No m / m·s⁻¹ threshold.
    amps = np.array([pos[ti] - pos[bi] for bi, ti in pairs])
    modal = float(np.median(amps))
    pairs = [p for p, amp in zip(pairs, amps) if amp >= amp_floor_frac * modal]
    if not pairs:
        return []
    # Structural strip of the unrack/rerack/putdown family from the ENDS.
    if strip_terminal:
        pairs = _strip_terminal_anomalies(pairs, pos)
    return pairs


def segment(t, a_vert, prominence_frac=DEFAULT_PROMINENCE_FRAC,
            min_cadence_s=DEFAULT_MIN_CADENCE_S, amp_floor_frac=DEFAULT_AMP_FLOOR_FRAC,
            strip_terminal=True):
    """Segment reps from vertical acceleration. Returns a WaveResult.

    `a_vert`: gravity-projected vertical acceleration (m/s², up-positive) — exactly
    what `velocity.vertical_acceleration` produces. ONE config for all lifts."""
    t = np.asarray(t, dtype=float)
    a = np.asarray(a_vert, dtype=float)
    if len(t) < 16:
        return WaveResult(fs=0.0)
    fs = 1.0 / float(np.median(np.diff(t)))
    pos = _bootstrap_displacement(t, a, fs)
    pairs = reps_from_wave(pos, fs, prominence_frac, min_cadence_s,
                           amp_floor_frac, strip_terminal)
    if not pairs:
        return WaveResult(displacement=pos, fs=fs)

    # ZUPT-anchored velocity at the real turnarounds (the principled drift control for
    # the shipped number). Anchors = every extremum bounding a kept rep.
    anchors = sorted({i for bi, ti in pairs for i in (bi, ti)})
    v = integrate_with_zupt(t, a, anchors)

    reps = []
    for k, (bi, ti) in enumerate(pairs, 1):
        seg_v = v[bi:ti + 1]
        seg_t = t[bi:ti + 1]
        if len(seg_v) < 2:
            continue
        reps.append(WaveRep(
            rep_index=k, bottom_idx=bi, top_idx=ti,
            start_time=float(seg_t[0]), end_time=float(seg_t[-1]),
            rom=float(pos[ti] - pos[bi]),
            mean_concentric_velocity=float(np.mean(np.abs(seg_v))),
            peak_concentric_velocity=float(np.max(np.abs(seg_v))),
        ))
    for k, r in enumerate(reps, 1):
        r.rep_index = k
    return WaveResult(reps=reps, displacement=pos, velocity=v,
                      anchors=np.array(anchors, dtype=int), fs=fs)
