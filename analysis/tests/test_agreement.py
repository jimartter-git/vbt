"""Tests for cross-source agreement metrics (vbt_analysis.agreement)."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vbt_analysis.agreement import (
    bias, compare_panel, per_rep_rmse, theil_sen_slope, usable,
)


def test_usable_drops_phantom_and_nan():
    vals = [0.5, 0.4, None, 0.3, float("nan"), 0.2]
    flags = ["", "", "phantom", "", "", "missed"]
    assert usable(vals, flags) == [0.5, 0.4, 0.3]


def test_rmse_and_bias_basic():
    src = [0.50, 0.45, 0.40]
    ref = [0.55, 0.50, 0.45]            # source reads 0.05 low everywhere
    assert math.isclose(bias(src, ref), -0.05, abs_tol=1e-9)
    assert math.isclose(per_rep_rmse(src, ref), 0.05, abs_tol=1e-9)


def test_rmse_nan_on_count_mismatch():
    assert math.isnan(per_rep_rmse([0.5, 0.4], [0.5, 0.4, 0.3]))
    assert math.isnan(bias([0.5, 0.4], [0.5, 0.4, 0.3]))


def test_theil_sen_tracks_clean_decline():
    # perfect linear decline of -0.02 m/s per rep
    vals = [0.50 - 0.02 * i for i in range(10)]
    assert math.isclose(theil_sen_slope(vals), -0.02, abs_tol=1e-9)


def test_theil_sen_robust_to_one_ghost():
    # same decline, but rep 5 is a ghost crossing (0.05). Median-of-slopes barely moves;
    # an OLS slope would be visibly dragged.
    clean = [0.50 - 0.02 * i for i in range(10)]
    ghosted = clean.copy()
    ghosted[5] = 0.05
    ols = np.polyfit(np.arange(10), ghosted, 1)[0]
    ts = theil_sen_slope(ghosted)
    assert abs(ts - (-0.02)) < 0.005          # robust: stays near the true slope
    assert abs(ols - (-0.02)) > abs(ts - (-0.02))  # and beats OLS on this outlier


def test_theil_sen_too_short():
    assert math.isnan(theil_sen_slope([0.5]))


def test_compare_panel_aligned():
    src = [0.50, 0.48, 0.46, 0.40]
    ref = [0.55, 0.53, 0.51, 0.45]
    p = compare_panel(src, ref)
    assert p["aligned"] is True
    assert math.isclose(p["bias"], -0.05, abs_tol=1e-9)
    assert p["rmse"] > 0
    # both decline, similar slope -> small slope delta
    assert abs(p["slope_delta"]) < 0.01
    # velocity loss is finite for >=3 reps and the deltas are computed
    assert np.isfinite(p["vl_source"]) and np.isfinite(p["vl_ref"])
    assert np.isfinite(p["vl_delta"])


def test_compare_panel_count_mismatch_gates_absolute_not_shape():
    # source over-counts (a ghost rep); absolute axis must abstain, shape still reported
    src = [0.50, 0.48, 0.10, 0.46, 0.40]    # 5 "reps", one ghost
    ref = [0.55, 0.53, 0.51, 0.45]          # 4 real reps
    p = compare_panel(src, ref)
    assert p["aligned"] is False
    assert math.isnan(p["rmse"]) and math.isnan(p["bias"])
    assert np.isfinite(p["vl_source"]) and np.isfinite(p["vl_ref"])


def test_compare_panel_excludes_phantom_for_alignment():
    # tagging the ghost as phantom restores the count match -> absolute axis engages
    src = [0.50, 0.48, 0.10, 0.46, 0.40]
    src_flags = ["", "", "phantom", "", ""]
    ref = [0.55, 0.53, 0.51, 0.45]
    p = compare_panel(src, ref, source_flags=src_flags)
    assert p["n_source"] == 4 and p["n_ref"] == 4
    assert p["aligned"] is True
    assert np.isfinite(p["rmse"])
