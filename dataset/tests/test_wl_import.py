"""Synthetic-fixture tests for the WL importer's name-based column selection.

We don't commit real WL exports (they live in dataset/raw/, gitignored), so we
fabricate slim (3-col) and rich (multi-col) exports with a known signal and
assert the importer picks the VERTICAL VELOCITY column by name, uses the
displacement channel for ROM, and reads acceleration — never the decoy
horizontal-velocity column.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from wl_import import parse_wl_txt, derive_rep_metrics  # noqa: E402

FS = 100.0
PERIOD = 2.0
N_REPS = 3
PEAK_V = 0.8
EXPECTED_MEAN = PEAK_V * 2 / np.pi  # mean of a positive half-sine * peak


def _signal():
    t = np.arange(0.0, N_REPS * PERIOD, 1.0 / FS)
    v = PEAK_V * np.sin(2 * np.pi * t / PERIOD)          # vertical velocity
    disp_m = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(t))])
    acc = np.gradient(v, t)
    return t, v, disp_m, acc


def _write_rich(path):
    t, v, disp_m, acc = _signal()
    hv = np.full_like(v, 9.9)  # DECOY horizontal velocity — must NOT be selected
    lines = [
        "Weight (lbs): 149.7",
        "velocity (vertical, m/s)",
        "video,average,min,time of min (ms),max,time of max (ms)",
        "1,0.40,-2.50,34900,1.20,35033",  # summary data row starting with a digit
        "",
        ('Frame number,Time (s),"velocity (vertical, m/s)","velocity (horizontal, m/s)",'
         '"acceleration (vertical, m/s^2)","displacement (vertical, m)"'),
    ]
    for i in range(len(t)):
        lines.append(f"{i+1},{t[i]:.2f},{v[i]:.4f},{hv[i]:.4f},{acc[i]:.4f},{disp_m[i]:.4f}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_slim(path):
    t, v, _, _ = _signal()
    lines = ["Weight (lbs): 149.7", 'Frame number,Time (s),"velocity (vertical, m/s)"']
    for i in range(len(t)):
        lines.append(f"{i+1},{t[i]:.2f},{v[i]:.4f}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def test_rich_export_selects_vertical_velocity_not_horizontal(tmp_path):
    p = tmp_path / "rich.txt"
    _write_rich(str(p))
    df, channels = parse_wl_txt(str(p))
    assert "vertical" in channels["velocity_vertical"].lower()
    reps, rom_from_disp = derive_rep_metrics(df)
    assert len(reps) == N_REPS
    for r in reps:
        # Would be ~9.9 if the decoy horizontal column were picked.
        assert abs(r["mean_velocity"] - EXPECTED_MEAN) < 0.06
        assert abs(r["peak_velocity"] - PEAK_V) < 0.08


def test_rich_export_uses_displacement_and_accel(tmp_path):
    p = tmp_path / "rich.txt"
    _write_rich(str(p))
    df, channels = parse_wl_txt(str(p))
    assert "displacement_vertical" in channels and "acceleration_vertical" in channels
    reps, rom_from_disp = derive_rep_metrics(df)
    assert rom_from_disp is True
    for r in reps:
        # half-sine displacement rise = PEAK_V * PERIOD / pi (m) -> cm
        assert abs(r["rom"] - (PEAK_V * PERIOD / np.pi * 100)) < 6
        assert "peak_accel" in r and r["peak_accel"] > 0


def _write_rich_tsv(path):
    """Same rich export but TAB-delimited (commas inside names, no quoting)."""
    t, v, disp_m, acc = _signal()
    hv = np.full_like(v, 9.9)
    cols = ["Frame number", "Time (s)", "velocity (vertical, m/s)",
            "velocity (horizontal, m/s)", "acceleration (vertical, m/s^2)",
            "displacement (vertical, m)"]
    lines = ["Weight (lbs): 149.7", "\t".join(cols)]
    for i in range(len(t)):
        lines.append("\t".join([str(i + 1), f"{t[i]:.2f}", f"{v[i]:.4f}",
                                 f"{hv[i]:.4f}", f"{acc[i]:.4f}", f"{disp_m[i]:.4f}"]))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def test_rich_tsv_export_selects_vertical_velocity(tmp_path):
    p = tmp_path / "rich.tsv.txt"
    _write_rich_tsv(str(p))
    df, channels = parse_wl_txt(str(p))
    assert "vertical" in channels["velocity_vertical"].lower()
    assert "displacement_vertical" in channels
    reps, rom_from_disp = derive_rep_metrics(df)
    assert len(reps) == N_REPS and rom_from_disp is True
    for r in reps:
        assert abs(r["mean_velocity"] - EXPECTED_MEAN) < 0.06   # not the 9.9 decoy


def test_slim_export_still_works(tmp_path):
    p = tmp_path / "slim.txt"
    _write_slim(str(p))
    df, channels = parse_wl_txt(str(p))
    assert list(channels.keys()) == ["velocity_vertical"]
    reps, rom_from_disp = derive_rep_metrics(df)
    assert rom_from_disp is False  # integrated fallback
    assert len(reps) == N_REPS
    assert all(abs(r["mean_velocity"] - EXPECTED_MEAN) < 0.06 for r in reps)
