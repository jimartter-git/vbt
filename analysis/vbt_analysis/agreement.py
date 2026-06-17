"""Cross-source per-rep agreement — BOTH axes, robust to ghost reps.

When we score a source (watch IMU, our CV, SmartBarbell) against a reference
(Vitruve), we care about two genuinely different questions, and we report BOTH:

  * ABSOLUTE   — "is each rep the right SPEED?"  -> per-rep RMSE + bias (m/s).
  * SHAPE      — "did it see the same FATIGUE DECLINE?" -> velocity-loss Δ (pp)
                 and a robust Theil–Sen decline slope Δ (m/s per rep).

Why NOT Pearson r as the shape metric (see docs/cv-fusion.md discussion):
  1. It is scale-free — it standardizes away the very m/s the product cares about,
     so it answers "did the wiggles line up?" not "did the curve match?".
  2. It pivots on the set MEAN: one ghost/phantom rep shifts that mean and flips
     the sign of many reps' deviations at once. On slow, narrow-range lifts (bench
     ~0.19–0.40 m/s) the real signal is a few hundredths of m/s buried in noise,
     so a single bad rep sends r negative — an artifact, not an inverse lift.

Both axes are computed on PHANTOM-EXCLUDED reps. Absolute metrics additionally
require a count match (positional alignment); on a count mismatch they return NaN
and `aligned=False` rather than silently comparing the wrong reps — alignment is a
prerequisite, not an afterthought (count/segmentation must be solved first).
Shape metrics are per-series, so they are always reported (with the usual
velocity-loss <3-rep floor).
"""
from __future__ import annotations

import numpy as np

from .metrics import INVALID_FLAGS, velocity_loss_pct

NAN = float("nan")


def usable(values, flags=None) -> list[float]:
    """Drop phantom/missed and None/NaN, preserving physical rep order."""
    fl = list(flags) if flags is not None else [None] * len(values)
    return [float(v) for v, f in zip(values, fl)
            if v is not None and v == v and (f or "") not in INVALID_FLAGS]


def theil_sen_slope(values) -> float:
    """Robust decline slope (m/s per rep) = median of all pairwise slopes of MV
    vs rep index. Resists the 1–2 outlier reps that wreck an OLS/Pearson fit.
    NaN if fewer than 2 points."""
    y = np.asarray(values, dtype=float)
    n = len(y)
    if n < 2:
        return NAN
    slopes = [(y[j] - y[i]) / (j - i) for i in range(n) for j in range(i + 1, n)]
    return float(np.median(slopes))


def per_rep_rmse(source, ref) -> float:
    s, r = np.asarray(source, float), np.asarray(ref, float)
    if len(s) == 0 or len(s) != len(r):
        return NAN
    return float(np.sqrt(np.mean((s - r) ** 2)))


def bias(source, ref) -> float:
    """Mean signed error (source − ref), m/s. Positive = source reads fast."""
    s, r = np.asarray(source, float), np.asarray(ref, float)
    if len(s) == 0 or len(s) != len(r):
        return NAN
    return float(np.mean(s - r))


def compare_panel(source, ref, source_flags=None, ref_flags=None) -> dict:
    """Both-axis agreement of `source` vs reference `ref` (per-rep mean velocities
    in physical rep order). Phantom-excluded throughout. Returns a dict with the
    absolute axis (rmse/bias, gated on count-match) and the shape axis (velocity
    loss + Theil–Sen slope, per-series)."""
    s = usable(source, source_flags)
    r = usable(ref, ref_flags)
    aligned = len(s) == len(r) and len(s) > 0
    vl_s, vl_r = velocity_loss_pct(s), velocity_loss_pct(r)
    sl_s, sl_r = theil_sen_slope(s), theil_sen_slope(r)
    vl_delta = (vl_s - vl_r) if (np.isfinite(vl_s) and np.isfinite(vl_r)) else NAN
    sl_delta = (sl_s - sl_r) if (np.isfinite(sl_s) and np.isfinite(sl_r)) else NAN
    return {
        "n_source": len(s), "n_ref": len(r), "aligned": aligned,
        # absolute axis (count-matched only)
        "rmse": per_rep_rmse(s, r) if aligned else NAN,
        "bias": bias(s, r) if aligned else NAN,
        # shape axis (per-series; always reported)
        "vl_source": vl_s, "vl_ref": vl_r, "vl_delta": vl_delta,
        "slope_source": sl_s, "slope_ref": sl_r, "slope_delta": sl_delta,
    }
