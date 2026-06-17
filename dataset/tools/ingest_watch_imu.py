"""Ingest Apple Watch IMU per-rep velocity/ROM into rep_metrics.csv.

The watch raw CSVs (200 Hz CMDeviceMotion) live in dataset/raw/*_watch.csv. This
derives per-rep mean concentric velocity (m/s) and ROM (cm) via the vbt_analysis
ZUPT pipeline and files them as vendor `watch_imu`, so compare.py / build_db can
treat the watch like any other source.

We ingest the GATED ("adjusted") rep set, not the raw detector output: raw
`detect_turnarounds` over-segments pauses (esp. supine bench: 14-31 phantom
segments), so its per-rep velocities aren't meaningful. Gating:
  - rows  -> velocity.gate_reps (ROM/MV relative to the set's robust median)
  - bench -> bench-tuned clean (0.20<=ROM<=0.55 m, MV>0.12; the row gate's
             absolute thresholds don't fit slow/short-ROM bench)

true_rep discipline (mirrors the SmartBarbell rule — never force positionally
across vendors): when the gated count == ground-truth reps we align rep_index ->
true_rep 1:1; otherwise true_rep is left blank and the set is flagged
count_mismatch (a dropped/extra rep makes the physical identity ambiguous).

Idempotent: removes any existing watch_imu rows for a target set before writing.
Run from the repo root:  python dataset/tools/ingest_watch_imu.py
"""
from __future__ import annotations

import csv
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "analysis"))

from vbt_analysis.ingest import load_session                         # noqa: E402
from vbt_analysis.rep_detect import detect_turnarounds               # noqa: E402
from vbt_analysis.velocity import (                                  # noqa: E402
    gate_reps, integrate_with_zupt, rep_metrics, vertical_acceleration,
)

RM = os.path.join(REPO, "dataset/rep_metrics.csv")

# watch-instrumented sets -> (lift, ground-truth rep count). ROW-1/DL had no watch.
TARGETS = {
    **{f"20260615-ROW-{i}": ("row", 10) for i in range(2, 6)},
    **{f"20260616-BN-{i}": ("bench", 10) for i in range(1, 6)},
    **{f"20260617-SQ-{i}": ("squat", 10) for i in range(1, 5)},
    **{f"20260617-RDL-{i}": ("rdl", 8) for i in range(1, 3)},
}


def gated_reps(sid: str, lift: str):
    """Clean the raw turnaround detector per lift. The raw detector over-segments
    top/bottom pauses (zero-ROM noise) on every lift; the cleanup differs by the
    lift's ROM/MV band:
      - row/squat -> velocity.gate_reps (ROM/MV relative to the robust median; both
        sit comfortably above its ROM>0.3, MV>0.45 core).
      - bench     -> tighter ROM·MV clean (slow/short supine reps fall below the
        gate's absolute MV core).
      - rdl       -> ROM-window clean (the hinge MV ~0.3 is below gate_reps' MV core,
        so it bails; ROM ~0.45-0.65 m cleanly isolates the 8 real reps). NB: RDL
        watch MV reads low vs Vitruve (anchor/hinge limitation; see set notes)."""
    path = os.path.join(REPO, f"dataset/raw/{sid}_watch.csv")
    df = load_session(path)
    t = df["t"].to_numpy(float)
    a = vertical_acceleration(df)
    anchors = detect_turnarounds(t, a)
    v = integrate_with_zupt(t, a, anchors)
    reps = rep_metrics(t, v, anchors)
    if lift in ("row", "squat"):
        return gate_reps(reps)
    if lift == "rdl":
        return [r for r in reps if 0.40 <= r.range_of_motion <= 0.70
                and r.mean_concentric_velocity > 0.10]
    return [r for r in reps if 0.20 <= r.range_of_motion <= 0.55      # bench
            and r.mean_concentric_velocity > 0.12]


def build_rows():
    rows = []
    summary = []
    for sid, (lift, gt) in TARGETS.items():
        reps = gated_reps(sid, lift)
        n = len(reps)
        aligned = (n == gt)
        flag = "" if aligned else "count_mismatch"
        for i, r in enumerate(reps, start=1):
            true_rep = i if aligned else ""
            rows.append([sid, "watch_imu", i, true_rep, "mean_velocity",
                         round(r.mean_concentric_velocity, 3), "m/s", flag, ""])
            rows.append([sid, "watch_imu", i, true_rep, "rom",
                         round(r.range_of_motion * 100.0, 1), "cm", flag, ""])
        summary.append((sid, lift, n, gt, aligned))
    return rows, summary


def main() -> int:
    new_rows, summary = build_rows()
    with open(RM, newline="") as f:
        existing = list(csv.reader(f))
    header, body = existing[0], existing[1:]
    target_ids = set(TARGETS)
    # drop any prior watch_imu rows for the target sets (idempotent re-run)
    body = [r for r in body if not (r[1] == "watch_imu" and r[0] in target_ids)]
    body.extend(new_rows)
    with open(RM, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)

    print(f"Wrote {len(new_rows)} watch_imu rows ({len(new_rows)//2} reps) for "
          f"{len(summary)} sets -> {os.path.relpath(RM, REPO)}")
    for sid, lift, n, gt, aligned in summary:
        tag = "aligned (true_rep set)" if aligned else "COUNT MISMATCH (true_rep blank, flagged)"
        print(f"  {sid:<16} {lift:<6} gated {n} vs GT {gt}  -> {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
