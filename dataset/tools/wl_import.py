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
    """Extract the (time_s, velocity) frame table from a WL export.

    Three real-export quirks we defend against (seen in the committed files):
    - One or MORE summary blocks ("velocity (vertical, m/s)" -> "video,average,..."
      -> "1,0.41,-2.51,...") sit above the frame table, and each summary data row
      starts with a digit, so it would be mistaken for a frame. The richest exports
      stack ~16 of these (velocity/accel/displacement/power/force x axes). We only
      parse rows BENEATH the "Frame number" header and ignore everything above it.
    - The frame table may carry many extra columns (vertical/horizontal/total
      velocity, accel, displacement, power, force). Column 2 (0-based) is always
      vertical velocity in both the slim and rich exports, so we read just that.
    - The "Time (s)" column loses its decimals past ~10s (every frame reads as a
      bare integer second), so deduping/segmenting on it would collapse most of the
      set. We therefore IGNORE the time column for spacing and rebuild a uniform
      time base from the frame numbers at the camera's frame rate.
    """
    frames, t_raw, vs = [], [], []
    in_table = False
    with open(path, errors="ignore") as f:
        for line in f:
            parts = [p.strip().strip('"') for p in re.split(r"[,\t]", line)]
            if parts and parts[0].lower().startswith("frame number"):
                in_table = True  # the per-frame table begins after this header
                continue
            if not in_table:
                continue  # skip the Weight line + every summary block above the table
            # A frame row is: <int frame>, <float time>, <float vertical velocity>, ...
            if len(parts) >= 3 and parts[0].isdigit():
                try:
                    fr = int(parts[0]); t = float(parts[1]); v = float(parts[2])
                except ValueError:
                    continue
                frames.append(fr); t_raw.append(t); vs.append(v)
    if not frames:
        raise ValueError(f"no frame rows parsed from {path}")
    df = pd.DataFrame({"frame": frames, "t_raw": t_raw, "v": vs})
    df = df.drop_duplicates("frame").sort_values("frame").reset_index(drop=True)
    # Robust dt from the part of the time column that still has sub-second
    # precision (ignore zero diffs from the integer-truncated tail and any jumps).
    dt_raw = np.diff(df["t_raw"].to_numpy())
    good = dt_raw[(dt_raw > 1e-4) & (dt_raw < 0.5)]
    dt = float(np.median(good)) if good.size else 0.04
    df["t"] = (df["frame"] - df["frame"].iloc[0]) * dt
    return df[["t", "v"]]


def segment_reps(t: np.ndarray, v: np.ndarray, peak_min: float = 0.3,
                 rom_min: float = 0.25):
    """Return per-rep concentric (positive-velocity) segments as (start,end) idx.

    WL gives velocity directly (drift-free), so we high-pass to remove any slow
    baseline and split on zero-crossings, taking positive runs as concentrics.
    Two kinds of non-rep positive blips have to be rejected:
    - the small ±0.1 m/s wobbles on the turnarounds between reps -> filtered by
      requiring the segment PEAK to clear `peak_min`;
    - on lifts where the bar is DROPPED from lockout (deadlift), it rebounds off
      the floor in a short, fast positive spike (seen up to ~1.3 m/s) that a peak
      threshold can't distinguish from a pull -> filtered by requiring the segment
      to travel a real ROM (`rom_min`): a true concentric covers ~0.5-0.7 m, a
      floor bounce only ~0.1 m.
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
        seg_v, seg_t = v[s:e + 1], t[s:e + 1]
        if seg_v.mean() <= 0 or seg_v.max() < peak_min:
            continue
        # displacement over the run; rejects floor bounces that never travel far
        if cumulative_trapezoid(seg_v, seg_t, initial=0.0)[-1] < rom_min:
            continue
        segs.append((s, e))
    return segs


def derive_rep_metrics(df: pd.DataFrame):
    t, v = df["t"].to_numpy(), df["v"].to_numpy()
    segs = segment_reps(t, v)
    out = []
    for i, (s, e) in enumerate(segs, start=1):
        seg_v, seg_t = v[s:e + 1], t[s:e + 1]
        rom_m = float(cumulative_trapezoid(seg_v, seg_t, initial=0.0)[-1])
        # Mean over the ACTIVE pull only. The zero-crossing boundaries can sweep in
        # the near-zero floor rest before a heavy rep (esp. the grindy terminal one),
        # which would deflate the mean even though peak/ROM are right; trim the
        # leading/trailing frames below 10% of peak so the mean matches what the
        # commercial apps report (lockout-to-lockout concentric). ROM stays the
        # full integral (the trimmed frames carry ~no displacement anyway).
        peak = float(seg_v.max())
        active = np.where(seg_v >= max(0.05, 0.1 * peak))[0]
        a0, a1 = int(active[0]), int(active[-1])
        mean_v = float(seg_v[a0:a1 + 1].mean())
        out.append({
            "rep_index": i,
            "mean_velocity": round(mean_v, 3),
            "peak_velocity": round(peak, 3),
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
            # Default true_rep = rep_index (WL segments the whole set). If WL's
            # count disagrees with your true rep count, fix true_rep afterward.
            rows.append(dict(set_id=args.set_id, vendor="wl_analysis",
                             rep_index=r["rep_index"], true_rep=r["rep_index"],
                             metric=metric,
                             value=r[metric], unit=("cm" if metric == "rom" else "m/s"),
                             flag="", confidence=""))
    for r in reps:
        print(f"  rep {r['rep_index']}: mean {r['mean_velocity']}  peak {r['peak_velocity']}  rom {r['rom']}cm")

    if args.append:
        header = ["set_id", "vendor", "rep_index", "true_rep", "metric", "value", "unit", "flag", "confidence"]
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
