"""Track A — the generalization guardrail instruments (no video, all synthetic/fast).

Covers: no-GT track-honesty checks (vbt_video.honesty), input provenance, and
blind/leave-one-out validation (vbt_analysis.validation).
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vbt_video import honesty  # noqa: E402
from vbt_analysis import validation as val  # noqa: E402


# --- synthetic trajectory builders -------------------------------------------
def _vertical_reps(n_reps=8, amp_px=120, x_px=300, fps=30.0, period_s=1.6, noise=1.0):
    """A clean working-plate track: plate bobs UP/DOWN n_reps times at fixed cadence,
    x roughly constant. Returns N×3 (t, cx, cy)."""
    t = np.arange(0, n_reps * period_s, 1.0 / fps)
    cy = 600 + amp_px * np.cos(2 * np.pi * t / period_s)   # image-y, bobbing
    cx = x_px + noise * np.sin(2 * np.pi * t / (period_s * 3))
    rng = np.random.default_rng(0)
    cy = cy + rng.normal(0, noise, len(t))
    cx = cx + rng.normal(0, noise, len(t))
    return np.column_stack([t, cx, cy])


def _horizontal_decoy(**kw):
    """A decoy oscillating HORIZONTALLY at rep cadence (swap x/y of a vertical track)."""
    tr = _vertical_reps(**kw)
    return np.column_stack([tr[:, 0], tr[:, 2], tr[:, 1]])


def _static_track(n=200, x=160, y=80, fps=30.0):
    """A barely-moving rack-stored plate (a few px of jitter)."""
    t = np.arange(0, n / fps, 1.0 / fps)
    rng = np.random.default_rng(1)
    return np.column_stack([t, x + rng.normal(0, 1.5, len(t)), y + rng.normal(0, 1.5, len(t))])


def _oneway_drift(n=200, fps=30.0):
    """A putdown / one-way move that never returns — aperiodic."""
    t = np.arange(0, n / fps, 1.0 / fps)
    return np.column_stack([t, 300 + 0 * t, 200 + 2.0 * np.arange(len(t))])


# --- honesty: metrics ---------------------------------------------------------
def test_vertical_dominance_separates_lift_from_horizontal_decoy():
    assert honesty.vertical_dominance(_vertical_reps()) > 3.0
    assert honesty.vertical_dominance(_horizontal_decoy()) < 0.5


def test_periodicity_strong_for_reps_weak_for_drift():
    per_reps, lag = honesty.periodicity(_vertical_reps()[:, 2])
    assert per_reps > 0.5 and lag > 0
    per_drift, _ = honesty.periodicity(_oneway_drift()[:, 2])
    assert per_drift < 0.3


def test_motion_presence_flags_static_plate():
    moving = honesty.motion_presence(_vertical_reps(amp_px=120), target_px=120)
    static = honesty.motion_presence(_static_track(), target_px=120)
    assert moving > 1.0           # travels well over a plate diameter
    assert static < 0.30          # barely moves


def test_motion_presence_unknown_target_is_nan():
    assert np.isnan(honesty.motion_presence(_vertical_reps(), target_px=None))


# --- honesty: combined verdict ------------------------------------------------
def test_track_honesty_passes_real_lift():
    h = honesty.track_honesty(_vertical_reps(), target_px=120)
    assert h["honest"] is True and h["flags"] == []


def test_track_honesty_flags_horizontal_decoy():
    h = honesty.track_honesty(_horizontal_decoy(), target_px=120)
    assert h["honest"] is False
    assert "not_vertical_dominant" in h["flags"]


def test_track_honesty_flags_static_rack_plate():
    h = honesty.track_honesty(_static_track(), target_px=120)
    assert h["honest"] is False
    assert "static_track" in h["flags"]


def test_track_honesty_flags_oneway_drift_as_aperiodic():
    h = honesty.track_honesty(_oneway_drift(), target_px=120)
    assert "aperiodic" in h["flags"]


# --- honesty: seed-jitter stability ------------------------------------------
def test_seed_jitter_stable_when_count_constant():
    perts = [(dx, dy, 0.0) for dx in (-4, 0, 4) for dy in (-4, 0, 4)]
    out = honesty.seed_jitter_stability(lambda dx, dy, dt: 10, perts)
    assert out["stable"] is True and out["agreement"] == 1.0 and out["base_count"] == 10


def test_seed_jitter_brittle_when_count_varies():
    # a decoy: count jumps around with the seed
    counts = iter([10, 3, 17, 0, 12, 2, 9, 21, 4])
    out = honesty.seed_jitter_stability(lambda dx, dy, dt: next(counts),
                                        [(0, 0, 0)] * 9, base_count=10)
    assert out["stable"] is False and out["agreement"] < 0.5


# --- provenance ---------------------------------------------------------------
def test_provenance_seed_free():
    assert val.provenance() == val.SEED_FREE
    assert val.is_blind(val.provenance()) is True


def test_provenance_simulated_tap_from_seed_or_rim():
    assert val.provenance(seed=(1, 2, 3, 4)) == val.SIMULATED_TAP
    assert val.provenance(rim_px=210) == val.SIMULATED_TAP
    assert val.is_blind(val.SIMULATED_TAP) is False


def test_provenance_oracle_dominates():
    # a manual crop band or per-clip scale hint is oracle even alongside a tap
    assert val.provenance(band=(0, 100)) == val.ORACLE
    assert val.provenance(scale={"angle": "side"}) == val.ORACLE
    assert val.provenance(seed=(1, 2, 3, 4), band=(0, 100)) == val.ORACLE


# --- blind / leave-one-out validation ----------------------------------------
def test_leave_one_out_holds_out_each_item():
    # fit = mean of the training values; score = squared error on the held-out value.
    items = [1.0, 2.0, 3.0, 4.0]
    fit = lambda tr: float(np.mean(tr))
    score = lambda it, p: (it - p) ** 2
    out = val.leave_one_out(items, fit, score)
    # held-out item 1.0 is scored vs mean(2,3,4)=3.0 → (1-3)^2 = 4
    assert out["scores"][0] == pytest.approx(4.0)
    assert out["n_groups"] == 4
    assert np.isfinite(out["blind_mean"])


def test_leave_one_out_groups_by_key():
    items = [("a", 1.0), ("a", 2.0), ("b", 10.0), ("b", 11.0)]
    fit = lambda tr: float(np.mean([v for _, v in tr]))
    score = lambda it, p: abs(it[1] - p)
    out = val.leave_one_out(items, fit, score, key=lambda it: it[0])
    assert out["n_groups"] == 2          # held out a whole session at a time


def test_blind_in_sample_delta_positive_when_overfit():
    # in-sample mean error < blind error → positive delta (the overfit signal)
    items = [0.0, 0.0, 0.0, 10.0]
    fit = lambda tr: float(np.mean(tr))
    score = lambda it, p: abs(it - p)
    out = val.blind_in_sample_delta(items, fit, score)
    assert out["delta"] > 0
    assert out["blind_mean"] >= out["in_sample_mean"]


# --- Track C / learned detector wiring (torch stays optional) ---
def test_learned_tracker_requires_model_path():
    # selecting the learned tracker without weights raises a clear error, not an import crash
    import pytest as _pt
    from vbt_video import VideoVelocitySource, VideoConfig
    import numpy as _np
    from vbt_video import ArrayFrameSource
    frames = [_np.zeros((64, 64, 3), _np.uint8) for _ in range(20)]
    with _pt.raises(ValueError):
        VideoVelocitySource(VideoConfig(tracker="learned", learned_model=None)).estimate(
            ArrayFrameSource(frames, 30.0))


def test_base_pipeline_import_does_not_require_torch():
    # importing the video pipeline must not drag in ultralytics/torch (lazy ML deps)
    import importlib, sys
    # vbt_video is already imported by the suite; assert the heavy dep wasn't pulled by it.
    # (learned.py imports ultralytics only inside functions.)
    import vbt_video.pipeline  # noqa: F401
    assert "ultralytics" not in sys.modules or "vbt_video.learned" in sys.modules
