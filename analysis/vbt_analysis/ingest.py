"""Load recorded sessions (and generate synthetic ones for testing).

CSV column contract — see ../../docs/data-schema.md and VBTCore/MotionSample:
    t,ua_x,ua_y,ua_z,g_x,g_y,g_z,q_w,q_x,q_y,q_z
"""

from __future__ import annotations

import numpy as np
import pandas as pd

COLUMNS = [
    "t",
    "ua_x", "ua_y", "ua_z",
    "g_x", "g_y", "g_z",
    "q_w", "q_x", "q_y", "q_z",
]


def load_session(csv_path: str) -> pd.DataFrame:
    """Load a recorded watch session CSV into a DataFrame, validating columns."""
    df = pd.read_csv(csv_path)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} missing required columns: {missing}")
    return df[COLUMNS].astype(float)


def sample_utc(csv_path: str, t):
    """Map sample `t` (device uptime, the CSV's `t` column) to absolute UTC epoch
    seconds, using the `<stem>.json` metadata sidecar's clock anchor (schema v2):
        sampleUTC = startedAt + (t − clockAnchorUptimeSeconds).
    Returns a numpy array (or None if no sidecar / pre-v2 metadata). The watch's
    `t` is uptime, not wall clock — this anchor is what makes cross-source (watch↔
    video/Vitruve) fusion possible; refine the sub-second offset with velocity
    cross-correlation (see docs/data-schema.md). See VBTCore/RecordingMetadata.
    """
    import json
    import os
    from datetime import datetime

    side = os.path.splitext(csv_path)[0] + ".json"
    if not os.path.exists(side):
        return None
    meta = json.load(open(side))
    anchor = meta.get("clockAnchorUptimeSeconds")
    started = meta.get("startedAt")
    if anchor is None or started is None:
        return None                                   # v1 sidecar: no usable anchor
    start_epoch = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
    return start_epoch + (np.asarray(t, dtype=float) - float(anchor))


def synthetic_set(
    n_reps: int = 5,
    peak_velocity: float = 0.8,
    rep_period: float = 2.0,
    fs: float = 200.0,
    noise_g: float = 0.0,
    seed: int = 0,
) -> pd.DataFrame:
    """Generate a synthetic recording of `n_reps` clean reps.

    Each rep is one full sine period of vertical velocity (concentric up, then
    eccentric down), so velocity is exactly zero at every turnaround — ideal
    ZUPT anchors. The watch is held perfectly upright (gravity = -Z), so the
    recovered vertical acceleration equals the modeled acceleration.

    Returns a DataFrame in the on-disk schema. Used by tests and demos.
    """
    rng = np.random.default_rng(seed)
    duration = n_reps * rep_period
    t = np.arange(0.0, duration, 1.0 / fs)

    omega = 2.0 * np.pi / rep_period
    v_true = peak_velocity * np.sin(omega * t)          # m/s, vertical (up +)
    a_true = peak_velocity * omega * np.cos(omega * t)  # m/s^2, vertical (up +)

    g_ms2 = 9.80665
    a_true_g = a_true / g_ms2                            # back into g units
    if noise_g > 0:
        a_true_g = a_true_g + rng.normal(0.0, noise_g, size=a_true_g.shape)

    n = len(t)
    df = pd.DataFrame({
        "t": t,
        # Watch upright: gravity points down body's -Z, vertical motion on +Z.
        # userAcceleration is in g; vertical (up) accel sits on +Z, gravity on -Z.
        "ua_x": np.zeros(n),
        "ua_y": np.zeros(n),
        "ua_z": a_true_g,
        "g_x": np.zeros(n),
        "g_y": np.zeros(n),
        "g_z": -np.ones(n),
        "q_w": np.ones(n),
        "q_x": np.zeros(n),
        "q_y": np.zeros(n),
        "q_z": np.zeros(n),
    })
    return df
