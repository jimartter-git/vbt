#!/usr/bin/env python3
"""Import a WL Analysis per-frame velocity export (.txt) into rep_metrics rows.

WL exports a per-frame vertical-velocity trace (no per-rep table). We segment it
into reps and compute per-rep mean concentric velocity ourselves — i.e. WL's raw
signal run through our own rep logic. Output rows are tagged vendor=wl_analysis.

The WL export looks like (after some header lines):
    Frame number, Time (s), velocity (vertical, m/s)
    1, 0.00, 0.00
    ...
Note: WL's "Weight (lbs)" header value is actually kg (mislabeled) — we don't
trust it; pass the real load via the set metadata, not this file.

Usage:
    python dataset/tools/wl_import.py <export.txt> <set_id> [--append]

Without --append it prints the derived rows (dry run). With --append it appends
them to dataset/rep_metrics.csv.

STATUS: written against the documented export format; verify column parsing
against a real WL .txt the first time (we don't have one committed yet).
"""
from __future__ import annotations
import argparse
import csv
import os
import re

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt

DATASET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPS_CSV = os.path.join(DATASET, "rep_metrics.csv")


def parse_wl_txt(path: str) -> pd.DataFrame:
    """Extract the (time_s, velocity) frame table from a WL export."""
    rows = []
    with open(path, errors="ignore") as f:
        for line in f:
            parts = [p.strip() for p in re.split(r"[,\t]", line)]
            # A frame row is: <int frame>, <float time>, <float velocity>
            if len(parts) >= 3 and parts[0].isdigit():
                try:
                    t = float(parts[1]); v = float(parts[2])
                except ValueError:
                    continue
                rows.append((t, v))
    if not rows:
        raise ValueError(f"no frame rows parsed from {path}")
    df = pd.DataFrame(rows, columns=["t", "v"]).drop_duplicates("t").reset_index(drop=True)
    return df


def segment_reps(t: np.ndarray, v: np.ndarray):
    """Return per-rep concentric (positive-velocity) segments as (start,end) idx.

    WL gives velocity directly (drift-free), so we high-pass to remove any slow
    baseline and split on zero-crossings, taking positive runs as concentrics.
    """
    fs = 1.0 / np.median(np.diff(t))
    b, a = butter(2, min(0.99, 0.1 / (fs / 2)), btype="high")
    vh = filtfilt(b, a, v)
    sign = np.sign(vh)
    sign[sign == 0] = 1
    crossings = np.where(np.diff(sign) != 0)[0]
    bounds = [0, *crossings.tolist(), len(v) - 1]
    segs = []
    for s, e in zip(bounds[:-1], bounds[1:]):
        if e - s < max(2, int(0.15 * fs)):
            continue
        if np.mean(v[s:e + 1]) > 0:   # concentric
            segs.append((s, e))
    return segs


def derive_rep_metrics(df: pd.DataFrame):
    t, v = df["t"].to_numpy(), df["v"].to_numpy()
    segs = segment_reps(t, v)
    out = []
    for i, (s, e) in enumerate(segs, start=1):
        seg_v, seg_t = v[s:e + 1], t[s:e + 1]
        rom_m = float(cumulative_trapezoid(seg_v, seg_t, initial=0.0)[-1])
        out.append({
            "rep_index": i,
            "mean_velocity": round(float(seg_v.mean()), 3),
            "peak_velocity": round(float(seg_v.max()), 3),
            "rom": round(rom_m * 100, 1),  # m -> cm
        })
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("txt"); p.add_argument("set_id")
    p.add_argument("--append", action="store_true")
    args = p.parse_args()

    df = parse_wl_txt(args.txt)
    reps = derive_rep_metrics(df)
    print(f"Parsed {len(df)} frames -> {len(reps)} concentric reps from {args.txt}")

    rows = []
    for r in reps:
        for metric in ("mean_velocity", "peak_velocity", "rom"):
            rows.append(dict(set_id=args.set_id, vendor="wl_analysis",
                             rep_index=r["rep_index"], metric=metric,
                             value=r[metric], unit=("cm" if metric == "rom" else "m/s"),
                             flag="", confidence=""))
    for r in reps:
        print(f"  rep {r['rep_index']}: mean {r['mean_velocity']}  peak {r['peak_velocity']}  rom {r['rom']}cm")

    if args.append:
        header = ["set_id", "vendor", "rep_index", "metric", "value", "unit", "flag", "confidence"]
        with open(REPS_CSV, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            for row in rows:
                w.writerow(row)
        print(f"Appended {len(rows)} rows to {REPS_CSV}")
    else:
        print("(dry run — pass --append to write to rep_metrics.csv)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
