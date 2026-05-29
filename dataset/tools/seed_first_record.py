#!/usr/bin/env python3
"""Bootstrap record #1: the 330 lb x 8 deadlift measured by multiple apps on
2026-05-29 (transcribed from screenshots shared in chat). Idempotent — appends
the set only if its set_id isn't already present.

This documents the provenance of the first record. Future records are appended
to the CSVs directly (by transcribing screenshots / importing exports), so this
script is a one-time bootstrap, not the ongoing entry path.

Run:  python dataset/tools/seed_first_record.py
"""
from __future__ import annotations
import csv
import os

DATASET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS_CSV = os.path.join(DATASET, "sets.csv")
REPS_CSV = os.path.join(DATASET, "rep_metrics.csv")

SET_ID = "20260529-DL-1"

SETS_HEADER = ["set_id", "date", "lift", "load_kg", "load_entered", "load_unit",
               "set_index", "target_reps", "actual_reps", "rpe_actual", "notes"]
REPS_HEADER = ["set_id", "vendor", "rep_index", "true_rep", "metric", "value", "unit", "flag", "confidence"]

set_row = {
    "set_id": SET_ID, "date": "2026-05-29", "lift": "deadlift",
    "load_kg": 149.7, "load_entered": 330, "load_unit": "lb",
    "set_index": 1, "target_reps": "", "actual_reps": 8, "rpe_actual": "",
    "notes": "multi-app comparison; SmartBarbell missed/zeroed rep 8",
}

# Per-rep transcriptions (rep 1..N). None = no value that rep.
DATA = {
    ("stance", "mean_velocity", "m/s"): [0.42, 0.47, 0.48, 0.45, 0.40, 0.32, 0.26, 0.20],
    ("stance", "peak_velocity", "m/s"): [0.73, 0.86, 0.83, 0.77, 0.71, 0.59, 0.48, 0.40],
    ("smartbarbell", "mean_velocity", "m/s"): [0.42, 0.42, 0.39, 0.31, 0.28, 0.28, 0.26],
    ("smartbarbell", "rom", "cm"): [60, 60, 60, 58, 58, 58, 58],
    ("smartbarbell", "concentric_time", "s"): [1.43, 1.43, 1.53, 1.87, 2.10, 2.03, 2.27],
    ("metric", "mean_velocity", "m/s"): [0.47, 0.52, 0.51, 0.51, 0.45, 0.43, 0.41, 0.32],
    ("metric", "rom", "cm"): [58, 59, 59, 60, 57, 59, 59, 59],
    ("metric", "time_to_peak", "s"): [0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.0, 1.3],
    ("metric", "ecc_power", "W"): [229, 280, 254, 319, 280, 208, 614, 121],
}

def build_rows():
    rows = []
    for (vendor, metric, unit), values in DATA.items():
        for i, v in enumerate(values, start=1):
            if v is None:
                continue
            # true_rep == rep_index here: every vendor's ordering aligns with the
            # physical sequence (SmartBarbell dropped the LAST rep, not a middle
            # one, so its 1-7 map to true 1-7). When a vendor drops a middle rep,
            # set true_rep to the asserted/inferred physical number instead.
            rows.append(dict(set_id=SET_ID, vendor=vendor, rep_index=i, true_rep=i,
                             metric=metric, value=v, unit=unit, flag="", confidence=""))
    # SmartBarbell's phantom 8th row (app emitted an all-zero rep) — its attempt
    # at true rep 8; flagged, kept out of stats, but it marks that rep 8 existed.
    rows.append(dict(set_id=SET_ID, vendor="smartbarbell", rep_index=8, true_rep=8,
                     metric="mean_velocity", value=0.0, unit="m/s",
                     flag="phantom", confidence=0))
    # WL Analysis: only the set-level average is transcribed (per-frame txt not
    # yet ingested — run wl_import.py once you have the export).
    rows.append(dict(set_id=SET_ID, vendor="wl_analysis", rep_index="", true_rep="",
                     metric="mean_velocity", value=0.40, unit="m/s",
                     flag="set_avg_only", confidence=""))
    return rows

def ensure_csv(path, header):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=header).writeheader()

def already_present(path, set_id):
    if not os.path.exists(path):
        return False
    with open(path, newline="") as f:
        return any(r.get("set_id") == set_id for r in csv.DictReader(f))

def main():
    ensure_csv(SETS_CSV, SETS_HEADER)
    ensure_csv(REPS_CSV, REPS_HEADER)
    if already_present(SETS_CSV, SET_ID):
        print(f"{SET_ID} already in sets.csv — nothing to do.")
        return
    with open(SETS_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=SETS_HEADER).writerow(set_row)
    rows = build_rows()
    with open(REPS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REPS_HEADER)
        for r in rows:
            w.writerow(r)
    print(f"Seeded {SET_ID}: 1 set, {len(rows)} rep_metrics rows.")

if __name__ == "__main__":
    main()
