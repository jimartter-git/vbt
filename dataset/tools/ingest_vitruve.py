"""Ingest a Vitruve per-rep CSV export into sets.csv + rep_metrics.csv.

Reusable importer (replaces the per-day _ingest_DATE_vitruve.py one-offs). Vitruve
is the established ground-truth reference; its `# Rep.` is 1-based and clean, so we
use it directly as both rep_index and true_rep. One export may hold several sets
(`# Set`); load is read from the per-rep `Weight (kg)` column and the lb entry is
derived (round kg / 0.45359).

Usage (from repo root):
  python dataset/tools/ingest_vitruve.py raw/20260617-SQ_vitruve.csv \
      --lift squat --date 2026-06-17 --prefix SQ [--note "..."]

Idempotent: removes any existing vitruve rows for the produced set_ids (and their
sets.csv rows) before appending, so re-running is safe.
"""
from __future__ import annotations

import argparse
import csv
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETS = os.path.join(REPO, "dataset", "sets.csv")
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")
LB_PER_KG = 0.45359

# Vitruve column -> (our metric, unit, transform)   [matches existing vitruve rows]
MET = [
    ("Mean Velocity (m/s)", "mean_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Mean Propulsive Velocity (m/s)", "mean_propulsive_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Peak Velocity (m/s)", "peak_velocity", "m/s", lambda x: round(float(x), 3)),
    ("ROM (Range of Motion) (m)", "rom", "cm", lambda x: round(float(x) * 100, 1)),
    ("Mean Power [MV] (W)", "mean_power", "W", lambda x: round(float(x), 2)),
    ("Peak Power (W)", "peak_power", "W", lambda x: round(float(x), 2)),
    ("Time to Peak Velocity (ms)", "time_to_peak", "s", lambda x: round(float(x) / 1000, 3)),
]


def _rewrite_without(path, key_fn):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], [r for r in rows[1:] if not key_fn(r)]
    return header, body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", help="path to the Vitruve export (relative to dataset/ or absolute)")
    ap.add_argument("--lift", required=True, help="canonical lift name, e.g. squat / romanian_deadlift")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--prefix", required=True, help="set_id lift code, e.g. SQ / RDL")
    ap.add_argument("--note", default="", help="extra note appended to each set row")
    args = ap.parse_args()

    src = args.csv if os.path.isabs(args.csv) else os.path.join(REPO, "dataset", args.csv)
    stamp = args.date.replace("-", "")

    by_set = {}
    for r in csv.DictReader(open(src)):
        by_set.setdefault(r["# Set"].strip(), []).append(r)

    set_rows, rep_rows, made = [], [], []
    for s in sorted(by_set, key=int):
        reps = by_set[s]
        sid = f"{stamp}-{args.prefix}-{s}"
        made.append(sid)
        load_kg = round(float(reps[0]["Weight (kg)"]), 1)
        load_lb = round(load_kg / LB_PER_KG)
        note = (f"{args.lift.replace('_', ' ').title()}, {args.date}. Vitruve GT (clean per-rep "
                f"export). Set {s} @ {load_lb} lb. Apple Watch IMU in "
                f"dataset/raw/{stamp}-{args.prefix}-{s}_watch.csv; HD video {stamp}-{args.prefix}-{s}.mov "
                f"in R2. RPE not provided -> blank.")
        if args.note:
            note += " " + args.note
        set_rows.append(dict(set_id=sid, date=args.date, lift=args.lift, load_kg=load_kg,
                             load_entered=load_lb, load_unit="lb", set_index=s, target_reps="",
                             actual_reps=len(reps), rpe_actual="", notes=note))
        for r in reps:
            rep = int(r["# Rep."])
            for col, metric, unit, fn in MET:
                v = r.get(col, "").strip()
                if v == "":
                    continue
                rep_rows.append(dict(set_id=sid, vendor="vitruve", rep_index=rep, true_rep=rep,
                                     metric=metric, value=fn(v), unit=unit, flag="", confidence=""))

    made_set = set(made)
    # idempotent: strip prior rows for these set_ids
    set_hdr, set_body = _rewrite_without(SETS, lambda r: r and r[0] in made_set)
    rep_hdr, rep_body = _rewrite_without(REPS, lambda r: r and r[0] in made_set and r[1] == "vitruve")
    with open(SETS, "w", newline="") as f:
        w = csv.writer(f); w.writerow(set_hdr)
        w.writerows([[sr[c] for c in set_hdr] for sr in set_rows])
        w.writerows(set_body)
    with open(REPS, "w", newline="") as f:
        w = csv.writer(f); w.writerow(rep_hdr)
        w.writerows(rep_body)
        w.writerows([[rr[c] for c in rep_hdr] for rr in rep_rows])

    print(f"ingested {len(set_rows)} sets, {len(rep_rows)} vitruve rep rows from {os.path.basename(src)}")
    for sr in set_rows:
        print(f"  {sr['set_id']}: {sr['load_entered']}lb x{sr['actual_reps']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
