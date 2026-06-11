"""Vertical acceleration projection, ZUPT integration, and per-rep metrics.

This is the heart of the estimator. Single integration of acceleration drifts;
Zero-Velocity Updates (ZUPT) defeat that drift by anchoring velocity to ~0 at
each rep turnaround. Per-rep boundary detection (rep_detect.py) is therefore a
prerequisite, not an afterthought.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import cumulative_trapezoid

G_MS2 = 9.80665


def vertical_acceleration(df) -> np.ndarray:
    """Project userAcceleration onto the gravity axis → scalar vertical accel.

    `gravity` gives the down direction in the device frame even as the wrist
    rotates, so projecting onto it yields a vertical (up-positive) acceleration
    robust to orientation. Returns m/s^2.
    """
    ua = df[["ua_x", "ua_y", "ua_z"]].to_numpy(dtype=float)
    g = df[["g_x", "g_y", "g_z"]].to_numpy(dtype=float)
    g_norm = np.linalg.norm(g, axis=1, keepdims=True)
    g_norm[g_norm == 0] = 1.0
    g_hat = g / g_norm                       # unit vector pointing DOWN
    a_vert_g = -np.einsum("ij,ij->i", ua, g_hat)  # up is positive
    return a_vert_g * G_MS2


def integrate_with_zupt(t: np.ndarray, a: np.ndarray, anchors) -> np.ndarray:
    """Integrate acceleration → velocity, applying a ZUPT at each anchor index.

    Within each segment between consecutive anchors we cumulatively integrate
    (velocity starts at 0) and then linearly de-drift so velocity also returns
    to 0 at the segment end — the classic two-sided zero-velocity constraint
    that removes accumulated integration drift.
    """
    t = np.asarray(t, dtype=float)
    a = np.asarray(a, dtype=float)
    v = np.zeros_like(a)

    bounds = sorted(set([0, *[int(i) for i in anchors], len(a) - 1]))
    for s, e in zip(bounds[:-1], bounds[1:]):
        if e <= s:
            continue
        seg_t = t[s : e + 1]
        seg_a = a[s : e + 1]
        raw = cumulative_trapezoid(seg_a, seg_t, initial=0.0)  # v(s)=0
        drift = np.linspace(0.0, raw[-1], len(raw))            # force v(e)=0
        v[s : e + 1] = raw - drift
    return v


@dataclass
class RepMetrics:
    rep_index: int
    start_time: float
    end_time: float
    mean_concentric_velocity: float  # m/s
    peak_concentric_velocity: float  # m/s
    range_of_motion: float           # m (single-integration estimate)


def rep_metrics(t: np.ndarray, v: np.ndarray, anchors) -> list[RepMetrics]:
    """Compute per-rep metrics from velocity, treating each positive-velocity
    segment between anchors as a concentric (lifting) phase.
    """
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    bounds = sorted(set([0, *[int(i) for i in anchors], len(v) - 1]))

    reps: list[RepMetrics] = []
    rep_idx = 0
    for s, e in zip(bounds[:-1], bounds[1:]):
        if e <= s:
            continue
        seg_v = v[s : e + 1]
        seg_t = t[s : e + 1]
        if np.mean(seg_v) <= 0:          # eccentric / lowering — skip
            continue
        rom = float(cumulative_trapezoid(seg_v, seg_t, initial=0.0)[-1])
        reps.append(
            RepMetrics(
                rep_index=rep_idx,
                start_time=float(seg_t[0]),
                end_time=float(seg_t[-1]),
                mean_concentric_velocity=float(np.mean(seg_v)),
                peak_concentric_velocity=float(np.max(seg_v)),
                range_of_motion=rom,
            )
        )
        rep_idx += 1
    return reps


def velocity_loss_pct(reps: list[RepMetrics]) -> float:
    """Intra-set velocity loss — the validated proximity-to-failure / fatigue proxy.

    Delegates to the project's ONE canonical definition (`vbt_analysis.metrics`):
    best rep → terminal window, never best→min (a mid-set slow rep must not
    inflate loss past the set's end). Returns 0.0 for sets too short to score.
    """
    from .metrics import velocity_loss_pct as _canonical
    vl = _canonical([r.mean_concentric_velocity for r in reps])
    return 0.0 if vl != vl else vl
