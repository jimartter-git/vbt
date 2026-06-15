"""Geometry tests for bilateral (two bar-end) fusion — analytic pinhole fixtures,
no rendering. Validates the two fusion tiers against known 3D ground truth:

* tilt cancellation: bar tilt moves the ends in antiphase → the average recovers
  the true bar-centre motion that EITHER single end gets wrong;
* depth correction: when the bar moves toward/away from the camera through the rep
  (the diagonal-clip ~2× physics), pos = −D·(cy−cy0)/d(t) is pinhole-EXACT and
  focal-length-free — the depth tier recovers truth where a constant ruler is biased.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video.track import Track  # noqa: E402
from vbt_video.bilateral import fuse_bilateral, bilateral_reps  # noqa: E402

F = 600.0                 # focal length (px) — used to BUILD the fixture only
H = 960                   # frame height; optical centre at H/2 (the module default)
CY0 = H / 2.0
D = 0.45                  # plate diameter (m)
A, T, NREP = 0.25, 2.0, 4  # rep amplitude (m), period (s), reps
FPS = 30.0


def _project(Y, Z):
    """Metric height Y at depth Z → pixel row (y grows downward) + apparent diameter."""
    return CY0 - F * Y / Z, F * D / Z


def _track(ts, Y, Z, conf=1.0):
    cy, d = _project(Y, Z)
    traj = np.column_stack([ts, np.full_like(ts, 100.0), cy])
    sizes = np.column_stack([ts, d])
    return Track(traj=traj, target_px=float(np.median(d)), confidence=conf,
                 size_cv=float(np.std(d) / np.mean(d)), sizes=sizes)


def _fixture(tilt=0.0, depth_arc=0.0, z1=3.0, z2=4.0):
    ts = np.arange(0, NREP * T, 1.0 / FPS)
    Y = -A * np.cos(2 * np.pi * ts / T)                  # true bar-centre height
    phase = (1 - np.cos(2 * np.pi * ts / T)) / 2.0       # 0 at bottom → 1 at top
    Y1 = Y + tilt * np.sin(2 * np.pi * ts / T)           # ends tilt in ANTIPHASE
    Y2 = Y - tilt * np.sin(2 * np.pi * ts / T)
    Z1 = z1 + depth_arc * phase                          # optional out-of-plane arc
    Z2 = z2 + depth_arc * phase
    return ts, Y, _track(ts, Y1, Z1), _track(ts, Y2, Z2)


def _rms(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def test_tilt_cancels_in_the_average():
    ts, Y, tr1, tr2 = _fixture(tilt=0.06)                # 6 cm end oscillation
    grid_t, fused, resid = fuse_bilateral(tr1, tr2, D, H, mode="avg")
    Yc = np.interp(grid_t, ts, Y - Y.mean())
    one_end = -tr1.traj[:, 2] * (D / tr1.target_px)
    one_end = np.interp(grid_t, ts, one_end - one_end.mean())
    assert _rms(fused, Yc) < 0.25 * _rms(one_end, Yc)    # fused ≫ better than either end
    assert np.max(np.abs(resid)) > 0.08                  # and the tilt shows up as L/R residual


def test_depth_correction_recovers_out_of_plane_motion():
    # The bar travels 0.6 m toward the camera through each rep (Z: 3.0→3.6) — the
    # diagonal-clip physics. A constant ruler is biased; the depth tier is exact.
    ts, Y, tr1, tr2 = _fixture(depth_arc=0.6, z1=3.0, z2=3.5)
    Yc = Y - Y.mean()
    _, fused_avg, _ = fuse_bilateral(tr1, tr2, D, H, mode="avg")
    grid_t, fused_dep, _ = fuse_bilateral(tr1, tr2, D, H, mode="depth")
    Yg = np.interp(grid_t, ts, Yc)
    assert _rms(fused_dep, Yg) < 0.02                    # pinhole-exact (− filter edge fx)
    assert _rms(fused_dep, Yg) < 0.3 * _rms(fused_avg, Yg)


def test_depth_mode_falls_back_without_size_trace():
    ts, Y, tr1, tr2 = _fixture()
    tr1.sizes = None
    grid_t, fused, _ = fuse_bilateral(tr1, tr2, D, H, mode="depth")
    Yg = np.interp(grid_t, ts, Y - Y.mean())
    assert _rms(fused, Yg) < 0.02                        # static depths → ruler exact anyway


def test_bilateral_reps_counts_and_flags():
    ts, Y, tr1, tr2 = _fixture(tilt=0.02)
    reps, meta = bilateral_reps(tr1, tr2, D, H, mode="avg")
    assert abs(len(reps) - NREP) <= 1
    for r in reps:
        assert abs(r["mean_velocity"] - 4 * A / T) < 0.08    # true mean concentric ≈ 0.5
        assert "lr_rms_m" in r
    assert meta["confidence"] == 1.0


def test_grossly_mistracked_end_raises_disagreement_flags():
    ts, Y, tr1, tr2 = _fixture()
    # end 2 tracks something at a fifth of the amplitude (a clearly wrong lock)
    bad = _track(ts, 0.2 * (Y - Y.mean()), np.full_like(ts, 4.0))
    reps, meta = bilateral_reps(tr1, bad, D, H, mode="avg")
    assert meta["n_lr_disagree"] >= max(1, len(reps) - 1)    # nearly every rep flagged
