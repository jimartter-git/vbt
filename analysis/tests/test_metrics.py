"""Tests for THE canonical velocity-loss definition (vbt_analysis.metrics).

Mirrors SetSummaryTests in Packages/VBTCore — the two implementations must stay
in lock-step (same fixtures, same expected numbers).
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_analysis.metrics import velocity_loss_pct, loss_window_label  # noqa: E402


def test_canonical_definition_matches_swift_fixture():
    # Same fixture as VBTCore SetSummaryTests: best → mean(last 2).
    assert velocity_loss_pct([0.80, 0.72, 0.60]) == pytest.approx(17.5)


def test_best_rep_referenced_not_rep1():
    # Warm-in: rep 2 is the fastest — loss references the BEST rep, not rep 1.
    assert velocity_loss_pct([0.70, 0.80, 0.60, 0.60]) == pytest.approx(25.0)


def test_midset_slow_rep_does_not_inflate_loss():
    # best→min would read 50% off the mid-set grinder; canonical runs to the END.
    vals = [0.80, 0.40, 0.78, 0.76]
    assert velocity_loss_pct(vals) == pytest.approx((0.80 - 0.77) / 0.80 * 100)


def test_too_short_returns_nan():
    assert np.isnan(velocity_loss_pct([0.8, 0.6]))
    assert np.isnan(velocity_loss_pct([]))


def test_phantom_rows_are_not_reps():
    # A trailing phantom (SmartBarbell's dropped-rep artifact) must not zero the loss.
    vals = [0.80, 0.70, 0.60, 0.0]
    flags = [None, None, None, "phantom"]
    assert velocity_loss_pct(vals, flags=flags) == pytest.approx(
        velocity_loss_pct([0.80, 0.70, 0.60]))


def test_exclude_partial_drops_flagged_terminal_rep_from_window():
    vals = [0.80, 0.70, 0.60, 0.30]
    flags = [None, None, None, "partial_rom"]
    incl = velocity_loss_pct(vals, flags=flags)                       # default: kept
    excl = velocity_loss_pct(vals, flags=flags, exclude_partial=True)
    assert incl == pytest.approx((0.80 - 0.45) / 0.80 * 100)
    assert excl == pytest.approx((0.80 - 0.65) / 0.80 * 100)


def test_exclude_partial_never_drops_below_validity_floor():
    # Excluding partials may not shrink the set below 3 usable reps.
    vals = [0.80, 0.70, 0.60]
    flags = [None, "partial_rom", "partial_rom"]
    assert velocity_loss_pct(vals, flags=flags, exclude_partial=True) == pytest.approx(
        velocity_loss_pct(vals))


def test_terminal_window_never_swallows_the_best_rep():
    # 3 reps with terminal_k=5: k clamps to n−1=2 → mean(0.70, 0.60)=0.65; the best
    # rep is never absorbed into its own terminal window.
    assert velocity_loss_pct([0.80, 0.70, 0.60], terminal_k=5) == pytest.approx(18.75)


def test_window_label_states_the_reps():
    assert loss_window_label(10) == "best→mean(rep9–10)"
    assert loss_window_label(10, terminal_k=1) == "best→rep10"
