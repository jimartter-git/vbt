"""Ingest Apple Watch IMU per-rep velocity/ROM into rep_metrics.csv.

The watch raw CSVs (200 Hz CMDeviceMotion) live in dataset/raw/*_watch.csv. This
derives per-rep mean concentric velocity (m/s) and ROM (cm) and files them so
compare.py / build_db can treat the watch like any other source.

Segmentation = the ONE-config, lift-agnostic WAVE segmenter (vbt_analysis.wave_segment,
learnings #27/#28): it reads reps off the vertical-displacement wave (modal up-excursions,
unrack/putdown stripped structurally) and re-derives per-rep velocity with ZUPT anchored at
the true turnarounds, mean over the ACTIVE concentric region (|v|>=10% peak — the same MV
definition the CV path uses). This REPLACES the old detect_turnarounds + per-lift gate
(rows/bench/rdl threshold regimes), which the wave reproduces (13/15 exact) without any
per-lift knobs — so deadlift/incline/split-squat ingest under the same code path.

Auto-discovery: every dataset/raw/*_watch.csv (wrist, vendor `watch_imu`) and
*_watch_bar.csv (watch fixed to the bar sleeve, vendor `watch_bar`) whose set_id has a
ground-truth rep count in sets.csv. No hand-maintained target list.

true_rep discipline (mirrors the SmartBarbell rule — never force positionally across
vendors): when the wave count == ground-truth reps we align rep_index -> true_rep 1:1;
otherwise true_rep is left blank and the set is flagged count_mismatch (a dropped/extra
rep makes the physical identity ambiguous).

Idempotent: removes any existing watch_imu / watch_bar rows for a touched set before
writing. Run from the repo root:  python dataset/tools/ingest_watch_imu.py
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "analysis"))

from vbt_analysis.ingest import load_session                         # noqa: E402
from vbt_analysis.velocity import vertical_acceleration              # noqa: E402
from vbt_analysis import wave_segment as ws                          # noqa: E402

RM = os.path.join(REPO, "dataset/rep_metrics.csv")
SETS = os.path.join(REPO, "dataset/sets.csv")
RAW = os.path.join(REPO, "dataset/raw")


def gt_counts() -> dict:
    """set_id -> ground-truth rep count, from sets.csv actual_reps."""
    out = {}
    with open(SETS, newline="") as f:
        for row in csv.DictReader(f):
            try:
                out[row["set_id"]] = int(row["actual_reps"])
            except (ValueError, KeyError):
                pass
    return out


def discover() -> list:
    """Find watch CSVs -> (path, set_id, vendor). Handles the _bar bar-sleeve mount."""
    out = []
    for path in sorted(glob.glob(os.path.join(RAW, "*_watch*.csv"))):
        fn = os.path.basename(path)
        m = re.match(r"(.+?)_watch(_bar)?\.csv$", fn)
        if not m:
            continue
        out.append((path, m.group(1), "watch_bar" if m.group(2) else "watch_imu"))
    return out


def wave_reps(path: str):
    df = load_session(path)
    t = df["t"].to_numpy(float)
    a = vertical_acceleration(df)
    return ws.segment(t, a).reps


def build_rows():
    gt = gt_counts()
    rows, summary = [], []
    touched = set()
    for path, sid, vendor in discover():
        g = gt.get(sid)
        if g is None:
            summary.append((sid, vendor, None, None, False, "no GT in sets.csv — skipped"))
            continue
        reps = wave_reps(path)
        n = len(reps)
        aligned = (n == g)
        flag = "" if aligned else "count_mismatch"
        touched.add(sid)
        for i, r in enumerate(reps, start=1):
            true_rep = i if aligned else ""
            rows.append([sid, vendor, i, true_rep, "mean_velocity",
                         round(r.mean_concentric_velocity, 3), "m/s", flag, ""])
            rows.append([sid, vendor, i, true_rep, "rom",
                         round(r.rom * 100.0, 1), "cm", flag, ""])
        summary.append((sid, vendor, n, g, aligned, ""))
    return rows, summary, touched


def main() -> int:
    new_rows, summary, touched = build_rows()
    with open(RM, newline="") as f:
        existing = list(csv.reader(f))
    header, body = existing[0], existing[1:]
    # drop any prior watch rows for the sets we re-ingest (idempotent re-run)
    body = [r for r in body if not (r[1] in ("watch_imu", "watch_bar") and r[0] in touched)]
    body.extend(new_rows)
    with open(RM, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)

    ingested = [s for s in summary if s[2] is not None]
    print(f"Wrote {len(new_rows)} watch rows ({len(new_rows)//2} reps) for "
          f"{len(ingested)} sets -> {os.path.relpath(RM, REPO)}")
    for sid, vendor, n, g, aligned, note in summary:
        if n is None:
            print(f"  {sid:<18} {vendor:<10} {note}")
            continue
        tag = "aligned (true_rep set)" if aligned else "COUNT MISMATCH (true_rep blank, flagged)"
        print(f"  {sid:<18} {vendor:<10} wave {n} vs GT {g}  -> {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
