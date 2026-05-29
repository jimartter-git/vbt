"""Tests for the ZUPT velocity estimator against synthetic ground truth.

The synthetic set models each rep as one sine period of vertical velocity, so
the true mean concentric velocity is peak * 2/pi and turnarounds sit exactly at
the velocity zero-crossings. These tests guard the integration math; real-data
accuracy is a separate question answered by Vitruve calibration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest

from vbt_analysis.ingest import synthetic_set
from vbt_analysis.rep_detect import detect_turnarounds
from vbt_analysis.velocity import (
    integrate_with_zupt,
    rep_metrics,
    velocity_loss_pct,
    vertical_acceleration,
)

PEAK_V = 0.8
N_REPS = 5
EXPECTED_MEAN_V = PEAK_V * 2.0 / np.pi  # mean of |sin| half-wave * peak


def _pipeline(noise_g=0.0):
    df = synthetic_set(n_reps=N_REPS, peak_velocity=PEAK_V, noise_g=noise_g)
    t = df["t"].to_numpy()
    a = vertical_acceleration(df)
    anchors = detect_turnarounds(t, a)
    v = integrate_with_zupt(t, a, anchors)
    return t, a, v, anchors


def test_vertical_projection_recovers_modeled_accel():
    df = synthetic_set(n_reps=2, peak_velocity=PEAK_V)
    a = vertical_acceleration(df)
    # Watch is upright with motion on +Z; projection must recover signed accel.
    expected = df["ua_z"].to_numpy() * 9.80665
    assert np.allclose(a, expected, atol=1e-9)


def test_detects_one_concentric_turnaround_per_rep():
    _, _, _, anchors = _pipeline()
    # N full sine periods => 2N interior zero-crossings (+ boundaries).
    assert len(anchors) == pytest.approx(2 * N_REPS, abs=2)


def test_integrator_matches_truth_with_exact_anchors():
    # Isolates the ZUPT integrator from the detector: given perfect turnaround
    # indices, recovered velocity should match ground truth almost exactly.
    df = synthetic_set(n_reps=N_REPS, peak_velocity=PEAK_V)
    t = df["t"].to_numpy()
    a = vertical_acceleration(df)
    v_true = PEAK_V * np.sin(np.pi * t)
    exact_anchors = [int(np.argmin(np.abs(t - k))) for k in range(1, 2 * N_REPS)]
    v = integrate_with_zupt(t, a, exact_anchors)
    rmse = np.sqrt(np.mean((v - v_true) ** 2))
    assert rmse < 0.01, f"integrator RMSE too high: {rmse:.4f} m/s"


def test_full_pipeline_velocity_matches_truth():
    # Detector + integrator together: looser bound, dominated by detection.
    t, _, v, _ = _pipeline()
    v_true = PEAK_V * np.sin(np.pi * t)
    rmse = np.sqrt(np.mean((v - v_true) ** 2))
    assert rmse < 0.06, f"pipeline velocity RMSE too high: {rmse:.4f} m/s"


def test_mean_concentric_velocity_within_tolerance():
    t, _, v, anchors = _pipeline()
    reps = rep_metrics(t, v, anchors)
    assert len(reps) == pytest.approx(N_REPS, abs=1)
    for r in reps:
        assert r.mean_concentric_velocity == pytest.approx(EXPECTED_MEAN_V, abs=0.05)
        assert r.peak_concentric_velocity == pytest.approx(PEAK_V, abs=0.1)


def test_robust_to_light_noise():
    t, _, v, anchors = _pipeline(noise_g=0.01)
    reps = rep_metrics(t, v, anchors)
    assert len(reps) >= N_REPS - 1
    mvs = [r.mean_concentric_velocity for r in reps]
    assert np.mean(mvs) == pytest.approx(EXPECTED_MEAN_V, abs=0.08)


def test_velocity_loss_is_nonnegative():
    t, _, v, anchors = _pipeline()
    reps = rep_metrics(t, v, anchors)
    assert velocity_loss_pct(reps) >= 0.0
