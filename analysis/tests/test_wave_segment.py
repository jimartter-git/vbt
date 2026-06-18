"""Track B — the lift-agnostic position-domain wave segmenter.

Two layers, both synthetic & fast:
  * the STRUCTURAL core (`reps_from_wave`) is tested on clean displacement waves built
    directly — deterministic, no integration round-trip — so the rep-picking logic
    (modal excursion, terminal strip, sub-modal rejection) is pinned exactly;
  * the full `segment` (accel → ZUPT velocity) gets a round-trip sanity test.

The real count validation is `scripts/wave_eval.py` on the watch corpus (13/15 exact,
ONE config) — these tests lock the LOGIC, not re-derive that number.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vbt_analysis import wave_segment as ws  # noqa: E402

_FPS = 50.0


def _bob(amp_m, period_s, dwell_s=0.4, fps=_FPS):
    """One cosine rep (0→amp→0) + a short bottom dwell — a clean displacement bump."""
    tb = np.arange(0, period_s, 1.0 / fps)
    up = 0.5 * amp_m * (1 - np.cos(2 * np.pi * tb / period_s))
    return np.concatenate([up, np.zeros(int(dwell_s * fps))])


def _wave(*bobs, pad_s=0.6, pad_h=0.25, fps=_FPS):
    """Concatenate displacement bobs with padding at both ends. The pad sits ABOVE the
    rep bottoms (0) by enough that the first/last bottoms are PROMINENT interior minima
    — mirroring a real capture where the watch is moving before/after the set
    (find_peaks can't flag an extremum sitting exactly at the signal edge, and a tiny
    pad makes the edge bottom sub-prominent)."""
    pad = np.full(int(pad_s * fps), pad_h)
    return np.concatenate([pad, *bobs, pad]), fps


# --- structural core: reps_from_wave on clean displacement -------------------
def test_counts_clean_rep_train():
    pos, fs = _wave(*[_bob(0.5, 2.0) for _ in range(8)])
    assert len(ws.reps_from_wave(pos, fs)) == 8


def test_one_config_across_amplitudes_and_cadences():
    # squat-like (big/slow), bench-like (small/faster), row-like — SAME config
    for n, amp, per in [(10, 0.6, 3.0), (10, 0.30, 1.8), (8, 0.45, 1.4)]:
        pos, fs = _wave(*[_bob(amp, per) for _ in range(n)])
        assert len(ws.reps_from_wave(pos, fs)) == n, (n, amp, per)


def test_terminal_putdown_excursion_stripped():
    # 8 full reps + a sub-modal (70%) terminal up-excursion (RDL putdown that half-rises)
    pos, fs = _wave(*[_bob(0.5, 2.0) for _ in range(8)], _bob(0.5 * 0.70, 2.0))
    assert len(ws.reps_from_wave(pos, fs, strip_terminal=True)) == 8
    assert len(ws.reps_from_wave(pos, fs, strip_terminal=False)) == 9   # not stripped


def test_full_amplitude_paused_last_rep_is_kept():
    # a real FULL-amplitude last rep after a long bottom pause must NOT be stripped
    # (the SQ-1 lesson — never drop a full-ROM main-lift rep)
    pos, fs = _wave(*[_bob(0.5, 2.0) for _ in range(9)],
                    np.zeros(int(_FPS * 8)), _bob(0.5, 2.0))
    assert len(ws.reps_from_wave(pos, fs)) == 10


def test_sub_modal_reposition_not_counted():
    # a parked sub-modal wiggle between reps is rejected (prominence + amp floor),
    # with no per-lift threshold
    pos, fs = _wave(*[_bob(0.5, 2.0) for _ in range(3)],
                    _bob(0.10, 1.5),                       # 10 cm reposition bob
                    *[_bob(0.5, 2.0) for _ in range(3)])
    assert len(ws.reps_from_wave(pos, fs)) == 6


def test_leading_unrack_stripped():
    # a sub-modal LEADING bob (an unrack to get into position) is stripped from the front
    pos, fs = _wave(_bob(0.5 * 0.6, 2.0), *[_bob(0.5, 2.0) for _ in range(8)])
    assert len(ws.reps_from_wave(pos, fs, strip_terminal=True)) == 8


def test_leading_unrack_isolated_by_gap_stripped():
    # a NEAR-MODAL leading excursion (an unrack press off the hooks) that is then
    # followed by a long settling gap before the set begins is stripped by the
    # leading-gap rule even though its amplitude is full (learning #32, IB-1/IB-2).
    pos, fs = _wave(_bob(0.5, 2.0), np.zeros(int(_FPS * 5)),
                    *[_bob(0.5, 2.0) for _ in range(8)])
    assert len(ws.reps_from_wave(pos, fs, strip_terminal=True)) == 8


def test_real_first_rep_with_normal_gap_kept():
    # the leading-gap rule keys on an anomalous gap AFTER the first excursion, NOT on
    # being first — a full-amplitude rep 1 with a normal inter-rep gap is kept (the
    # asymmetry guard: a settling breath sits BEFORE rep 1 with no excursion to strip).
    pos, fs = _wave(*[_bob(0.5, 2.0) for _ in range(9)])
    assert len(ws.reps_from_wave(pos, fs, strip_terminal=True)) == 9


# --- full accel→velocity round trip ------------------------------------------
def _accel_from_displacement(pos, fps=_FPS):
    return np.gradient(np.gradient(pos, 1.0 / fps), 1.0 / fps)


def test_segment_from_accel_roundtrip():
    pos, fs = _wave(*[_bob(0.5, 2.0) for _ in range(8)])
    t = np.arange(len(pos)) / fs
    res = ws.segment(t, _accel_from_displacement(pos))
    assert abs(res.count - 8) <= 1            # integration round-trip tolerance
    mvs = [r.mean_concentric_velocity for r in res.reps]
    assert all(m > 0 for m in mvs)            # concentric velocity positive
    assert res.velocity is not None and res.anchors is not None


def test_too_short_returns_empty():
    t = np.linspace(0, 0.1, 8)
    assert ws.segment(t, np.zeros(8)).count == 0
