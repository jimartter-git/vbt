#!/usr/bin/env python3
"""Analyze one recorded watch session: detect reps, estimate velocity, plot.

Usage:
    python scripts/analyze_session.py path/to/<sessionId>.csv [--out fig.png]
    python scripts/analyze_session.py --demo            # synthetic 5-rep set

Run from the analysis/ directory (or with analysis/ on PYTHONPATH).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from vbt_analysis.ingest import load_session, synthetic_set
from vbt_analysis.rep_detect import detect_turnarounds
from vbt_analysis.velocity import (
    integrate_with_zupt,
    rep_metrics,
    velocity_loss_pct,
    vertical_acceleration,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", nargs="?", help="session CSV path")
    p.add_argument("--demo", action="store_true", help="use a synthetic set")
    p.add_argument("--out", help="save plot to this path instead of showing")
    args = p.parse_args()

    if args.demo:
        df = synthetic_set(n_reps=5, peak_velocity=0.8, noise_g=0.01)
        print("Using synthetic 5-rep set (peak v = 0.8 m/s).")
    elif args.csv:
        df = load_session(args.csv)
        print(f"Loaded {len(df)} samples from {args.csv}")
    else:
        p.error("provide a CSV path or --demo")

    t = df["t"].to_numpy()
    a_vert = vertical_acceleration(df)
    anchors = detect_turnarounds(t, a_vert)
    v = integrate_with_zupt(t, a_vert, anchors)
    reps = rep_metrics(t, v, anchors)

    fs = 1.0 / np.median(np.diff(t)) if len(t) > 1 else float("nan")
    print(f"\nSample rate ~ {fs:.1f} Hz   |   turnarounds detected: {len(anchors)}")
    print(f"Concentric reps detected: {len(reps)}")
    print(f"{'rep':>3}  {'mean v':>8}  {'peak v':>8}  {'ROM (m)':>8}")
    for r in reps:
        print(f"{r.rep_index:>3}  {r.mean_concentric_velocity:>8.3f}  "
              f"{r.peak_concentric_velocity:>8.3f}  {r.range_of_motion:>8.3f}")
    print(f"\nIntra-set velocity loss: {velocity_loss_pct(reps):.1f}%")

    _plot(t, a_vert, v, anchors, args.out)
    return 0


def _plot(t, a_vert, v, anchors, out):
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    ax1.plot(t, a_vert, lw=0.8)
    ax1.set_ylabel("vertical accel (m/s²)")
    ax1.set_title("Vertical acceleration & ZUPT-integrated velocity")
    for c in anchors:
        ax1.axvline(t[c], color="r", alpha=0.3, lw=0.8)

    ax2.plot(t, v, lw=0.9, color="tab:green")
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylabel("velocity (m/s)")
    ax2.set_xlabel("time (s)")
    for c in anchors:
        ax2.axvline(t[c], color="r", alpha=0.3, lw=0.8)

    fig.tight_layout()
    if out:
        fig.savefig(out, dpi=120)
        print(f"\nSaved plot to {out}")
    else:
        plt.show()


if __name__ == "__main__":
    raise SystemExit(main())
