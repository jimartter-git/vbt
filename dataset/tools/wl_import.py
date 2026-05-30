#!/usr/bin/env python3
"""Import a WL Analysis per-frame export (.txt) into rep_metrics rows.

WL exports a per-frame trace (no per-rep table). We segment it into reps and
compute per-rep metrics ourselves — WL's raw signal run through our own rep
logic. Output rows are tagged vendor=wl_analysis.

Column selection is **name-based**: the frame table is matched by header name
(`velocity (vertical, m/s)`), so a 3-column "slim" export and a 16-column "rich"
export (velocity/accel/displacement/power/force x vertical/horizontal/total) both
parse correctly regardless of column order. Falls back to the historical fixed
position (col 2 = vertical velocity) only if no usable header is found.

Extra channels used when present:
- `displacement (vertical, …)` -> direct, drift-free ROM (better than integrating
  velocity).
- `acceleration (vertical, …)` -> per-rep peak acceleration (RFD proxy; also the
  watch's native signal, useful for later fusion cross-checks).

Quirks handled (seen in real exports):
- one or more summary blocks above the frame table whose data rows start with a
  digit (would look like frames) — we only read rows beneath the `Frame number`
  header.
- the `Time (s)` column loses its decimals past ~10s (every frame reads as a bare
  integer second) — we IGNORE it for spacing and rebuild a uniform time base from
  the frame numbers at the camera's frame rate.
- WL's `Weight (lbs)` header is actually kg and unreliable — ignore it; pass the
  real load via the set metadata.

Usage:
    python dataset/tools/wl_import.py <export.txt> <set_id> [--append]
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

UNIT = {"mean_velocity": "m/s", "peak_velocity": "m/s", "rom": "cm", "peak_accel": "m/s^2"}


def _tokenize(line):
    """Split a WL line into fields. WL column names contain commas
    (`velocity (vertical, m/s)`), so a plain comma split fragments the header.
    Real exports are tab-delimited or quote such fields — handle both."""
    line = line.rstrip("\n")
    if not line.strip():
        return []
    if "\t" in line:
        return [c.strip().strip('"') for c in line.split("\t")]
    return [c.strip() for c in next(csv.reader([line]), [])]


def _find_col(names, *needles):
    """First header whose lowercased name contains all needle substrings."""
    for n in names:
        low = (n or "").lower()
        if all(k in low for k in needles):
            return n
    return None


def _unit_in_name(name):
    """Pull the unit out of a 'param (axis, unit)' header, e.g. 'm', 'cm', 'm/s'."""
    m = re.search(r"\(([^)]*)\)", name or "")
    if m:
        bits = [b.strip() for b in m.group(1).split(",")]
        if len(bits) >= 2:
            return bits[-1].lower()
    return ""


def parse_wl_txt(path: str):
    """Return (DataFrame with t, v [+ disp_cm, acc when present], channels dict)."""
    header = None
    raw_rows = []
    with open(path, errors="ignore") as f:
        for line in f:
            parts = _tokenize(line)
            if parts and parts[0].lower().startswith("frame number"):
                header = parts            # the per-frame table header
                raw_rows = []             # (re)start beneath it; ignore summaries above
                continue
            if header is None:
                continue                  # skip Weight line + every summary block
            if parts and parts[0].isdigit() and len(parts) >= 2:
                raw_rows.append(parts)
    if not raw_rows:
        raise ValueError(f"no frame rows parsed from {path}")
    if header is None:                    # no named header -> assume slim layout
        header = ["Frame number", "Time (s)", "velocity (vertical, m/s)"]

    frame_col = _find_col(header, "frame") or header[0]
    time_col = _find_col(header, "time")
    vel_col = _find_col(header, "velocity", "vertical")
    if vel_col is None:                   # fallback: col 2 is vertical velocity in WL exports
        vel_col = header[2] if len(header) > 2 else None
    if vel_col is None:
        raise ValueError(f"could not locate a vertical-velocity column in: {header}")
    disp_col = _find_col(header, "displacement", "vertical")
    acc_col = _find_col(header, "acceleration", "vertical")

    idx = {name: i for i, name in enumerate(header)}

    def col(name):
        i = idx.get(name)
        vals = []
        for r in raw_rows:
            try:
                vals.append(float(r[i]) if (i is not None and i < len(r)) else np.nan)
            except ValueError:
                vals.append(np.nan)
        return np.array(vals)

    frames = np.array([int(r[idx[frame_col]]) for r in raw_rows])
    df = pd.DataFrame({"frame": frames, "v": col(vel_col)})
    df["t_raw"] = col(time_col) if time_col else np.arange(len(frames), dtype=float)
    if disp_col is not None:
        df["disp_raw"] = col(disp_col)
    if acc_col is not None:
        df["acc"] = col(acc_col)
    df = df.drop_duplicates("frame").sort_values("frame").reset_index(drop=True)

    # Rebuild a uniform time base from frame numbers (the time column truncates).
    dt_raw = np.diff(df["t_raw"].to_numpy())
    good = dt_raw[(dt_raw > 1e-4) & (dt_raw < 0.5)]
    dt = float(np.median(good)) if good.size else 0.04
    df["t"] = (df["frame"] - df["frame"].iloc[0]) * dt

    channels = {"velocity_vertical": vel_col}
    if disp_col is not None:
        scale = 1.0 if _unit_in_name(disp_col).startswith("cm") else 100.0  # ->cm
        df["disp_cm"] = df["disp_raw"] * scale
        channels["displacement_vertical"] = disp_col
    if acc_col is not None:
        channels["acceleration_vertical"] = acc_col

    keep = ["t", "v"] + (["disp_cm"] if disp_col is not None else []) + (["acc"] if acc_col is not None else [])
    return df[keep].copy(), channels


def segment_reps(t: np.ndarray, v: np.ndarray, peak_min: float = 0.3,
                 rom_min: float = 0.25):
    """Return per-rep concentric (positive-velocity) segments as (start,end) idx.

    WL gives velocity directly (drift-free), so we high-pass to remove any slow
    baseline and split on zero-crossings, taking positive runs as concentrics.
    Two non-rep positive blips are rejected:
    - small ±0.1 m/s wobbles on the turnarounds -> require segment PEAK >= peak_min;
    - on dropped-from-lockout lifts (deadlift) the bar rebounds off the floor in a
      short fast spike -> require real travel (`rom_min`); a true pull covers
      ~0.5-0.7 m, a floor bounce only ~0.1 m.
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
        if cumulative_trapezoid(seg_v, seg_t, initial=0.0)[-1] < rom_min:
            continue
        segs.append((s, e))
    return segs


def derive_rep_metrics(df: pd.DataFrame):
    t, v = df["t"].to_numpy(), df["v"].to_numpy()
    disp = df["disp_cm"].to_numpy() if "disp_cm" in df.columns else None
    acc = df["acc"].to_numpy() if "acc" in df.columns else None
    segs = segment_reps(t, v)
    out = []
    for i, (s, e) in enumerate(segs, start=1):
        seg_v, seg_t = v[s:e + 1], t[s:e + 1]
        peak = float(seg_v.max())
        # Mean over the ACTIVE pull only — zero-crossing bounds can sweep in the
        # near-zero floor rest before a heavy rep and deflate the mean; trim
        # leading/trailing frames below 10% of peak (matches lockout-to-lockout
        # concentric the commercial apps report).
        active = np.where(seg_v >= max(0.05, 0.1 * peak))[0]
        a0, a1 = int(active[0]), int(active[-1])
        rec = {"rep_index": i,
               "mean_velocity": round(float(seg_v[a0:a1 + 1].mean()), 3),
               "peak_velocity": round(peak, 3)}
        if disp is not None:                       # direct, drift-free ROM
            seg_d = disp[s:e + 1]
            rec["rom"] = round(float(np.nanmax(seg_d) - np.nanmin(seg_d)), 1)
        else:                                      # integrate velocity (fallback)
            rec["rom"] = round(float(cumulative_trapezoid(seg_v, seg_t, initial=0.0)[-1]) * 100, 1)
        if acc is not None:
            rec["peak_accel"] = round(float(np.nanmax(acc[s:e + 1])), 2)
        out.append(rec)
    return out, (disp is not None)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("txt"); p.add_argument("set_id")
    p.add_argument("--append", action="store_true")
    args = p.parse_args()

    df, channels = parse_wl_txt(args.txt)
    print(f"Channels found: {', '.join(f'{k}={v!r}' for k, v in channels.items())}")
    reps, rom_from_disp = derive_rep_metrics(df)
    print(f"Parsed {len(df)} frames -> {len(reps)} concentric reps from {args.txt}")
    print(f"ROM source: {'displacement channel (direct)' if rom_from_disp else 'integrated velocity (fallback)'}")

    rows = []
    for r in reps:
        for metric, val in r.items():
            if metric == "rep_index":
                continue
            flag = "" if not (metric == "rom" and not rom_from_disp) else "rom_integrated"
            rows.append(dict(set_id=args.set_id, vendor="wl_analysis",
                             rep_index=r["rep_index"], true_rep=r["rep_index"],
                             metric=metric, value=val, unit=UNIT[metric],
                             flag=flag, confidence=""))
        extra = f"  accel {r['peak_accel']}" if "peak_accel" in r else ""
        print(f"  rep {r['rep_index']}: mean {r['mean_velocity']}  peak {r['peak_velocity']}  rom {r['rom']}cm{extra}")

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
