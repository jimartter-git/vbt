"""Compare watch-derived per-rep velocity against Vitruve ground truth.

Alignment is by REP INDEX (watch rep i <-> Vitruve rep i), per
docs/calibration-protocol.md — no clock sync required. Stub until real Vitruve
exports land; the math (bias, RMSE, Bland-Altman) is ready to run.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ComparisonStats:
    n: int
    bias: float          # mean(watch - vitruve), m/s
    rmse: float          # m/s
    corr: float          # Pearson r
    loa_lower: float     # Bland-Altman 95% limits of agreement
    loa_upper: float
    slope: float         # watch = slope * vitruve + intercept
    intercept: float


def compare(watch_mv: np.ndarray, vitruve_mv: np.ndarray) -> ComparisonStats:
    """Per-rep comparison of mean concentric velocity. Inputs must be aligned
    by rep index and equal length."""
    watch = np.asarray(watch_mv, dtype=float)
    vit = np.asarray(vitruve_mv, dtype=float)
    if watch.shape != vit.shape:
        raise ValueError(f"length mismatch: watch {watch.shape} vs vitruve {vit.shape}")
    if len(watch) < 2:
        raise ValueError("need >= 2 paired reps to compare")

    diff = watch - vit
    bias = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff**2)))
    corr = float(np.corrcoef(watch, vit)[0, 1])
    sd = float(np.std(diff, ddof=1))
    slope, intercept = np.polyfit(vit, watch, 1)

    return ComparisonStats(
        n=len(watch),
        bias=bias,
        rmse=rmse,
        corr=corr,
        loa_lower=bias - 1.96 * sd,
        loa_upper=bias + 1.96 * sd,
        slope=float(slope),
        intercept=float(intercept),
    )


def plot_comparison(watch_mv, vitruve_mv, out_path: str | None = None):
    """Scatter (watch vs Vitruve, with regression + identity line) and a
    Bland-Altman plot. Saves to out_path if given, else shows."""
    import matplotlib.pyplot as plt

    watch = np.asarray(watch_mv, dtype=float)
    vit = np.asarray(vitruve_mv, dtype=float)
    stats = compare(watch, vit)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    ax1.scatter(vit, watch, alpha=0.7)
    lo, hi = min(vit.min(), watch.min()), max(vit.max(), watch.max())
    ax1.plot([lo, hi], [lo, hi], "k--", lw=1, label="identity")
    xs = np.linspace(lo, hi, 50)
    ax1.plot(xs, stats.slope * xs + stats.intercept, "r-", lw=1.5,
             label=f"fit (r={stats.corr:.3f})")
    ax1.set_xlabel("Vitruve mean velocity (m/s)")
    ax1.set_ylabel("Watch mean velocity (m/s)")
    ax1.set_title(f"Watch vs Vitruve  (RMSE={stats.rmse:.3f} m/s)")
    ax1.legend()

    mean_v = (watch + vit) / 2
    diff = watch - vit
    ax2.scatter(mean_v, diff, alpha=0.7)
    ax2.axhline(stats.bias, color="k", lw=1, label=f"bias={stats.bias:.3f}")
    ax2.axhline(stats.loa_upper, color="r", ls="--", lw=1, label="95% LoA")
    ax2.axhline(stats.loa_lower, color="r", ls="--", lw=1)
    ax2.set_xlabel("Mean of watch & Vitruve (m/s)")
    ax2.set_ylabel("Watch - Vitruve (m/s)")
    ax2.set_title("Bland-Altman")
    ax2.legend()

    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=120)
    else:
        plt.show()
    return stats
