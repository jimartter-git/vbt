"""Ingest the 2026-06-15 Barbell Row Vitruve export into sets.csv + rep_metrics.csv.

Set 1's raw export has 12 reps; the first 2 were a leftover warmup the lifter forgot
to end (lifter-confirmed) -> real set = 10 reps (Vitruve raw reps 3-12 -> true_rep 1-10),
rep_index preserves the raw Vitruve number for audit. Sets 2-5 are clean 10s.
Vitruve-for-rows caveat (INGESTION.md): unreliable on TnG rows; today it counted cleanly.
"""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "dataset", "20260615-ROW_vitruve.csv")
SETS = os.path.join(REPO, "dataset", "sets.csv")
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")

# column name -> (our metric, unit, transform)
MET = [
    ("Mean Velocity (m/s)", "mean_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Mean Propulsive Velocity (m/s)", "mean_propulsive_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Peak Velocity (m/s)", "peak_velocity", "m/s", lambda x: round(float(x), 3)),
    ("ROM (Range of Motion) (m)", "rom", "cm", lambda x: round(float(x) * 100, 1)),
    ("Mean Power [MV] (W)", "mean_power", "W", lambda x: round(float(x), 2)),
    ("Peak Power (W)", "peak_power", "W", lambda x: round(float(x), 2)),
    ("Time to Peak Velocity (ms)", "time_to_peak", "s", lambda x: round(float(x) / 1000, 3)),
]

rows = list(csv.DictReader(open(SRC)))
by_set = {}
for r in rows:
    by_set.setdefault(r["# Set"].strip(), []).append(r)

DROP = {"1": {1, 2}}            # set 1: drop raw reps 1 and 2 (leftover warmup)
LB = {"1": 135, "2": 145, "3": 145, "4": 145, "5": 145}

new_set_rows, new_rep_rows = [], []
for s in sorted(by_set, key=int):
    reps = [r for r in by_set[s] if int(r["# Rep."]) not in DROP.get(s, set())]
    sid = f"20260615-ROW-{s}"
    load_kg = round(float(reps[0]["Weight (kg)"]), 1)
    note = ("Barbell Row, 2026-06-15. Vitruve GT (clean per-rep counts this session - "
            "dead-stop/paused rows, unlike the 06-08 TnG rows Vitruve collapsed; INGESTION.md "
            "row-caveat noted). " + (
                "RAW export had 12 reps; first 2 were a leftover warmup the lifter forgot to "
                "end -> real set = 10 (Vitruve raw reps 3-12 -> true_rep 1-10; rep_index keeps "
                "the raw number). " if s == "1" else "") +
            "Watch IMU in dataset/raw/20260615-ROW-%s_watch.csv; video in R2; SmartBarbell pending." % s)
    new_set_rows.append(dict(set_id=sid, date="2026-06-15", lift="barbell_row",
                             load_kg=load_kg, load_entered=LB[s], load_unit="lb",
                             set_index=s, target_reps="", actual_reps=len(reps),
                             rpe_actual="", notes=note))
    for i, r in enumerate(reps, 1):                 # i = true_rep (1..10), re-indexed
        raw = int(r["# Rep."])                       # Vitruve's raw number (3..12 for set 1)
        for col, metric, unit, fn in MET:
            v = r.get(col, "").strip()
            if v == "":
                continue
            new_rep_rows.append(dict(set_id=sid, vendor="vitruve", rep_index=raw, true_rep=i,
                                     metric=metric, value=fn(v), unit=unit, flag="", confidence=""))

# append
with open(SETS) as f:
    set_cols = next(csv.reader(f))
with open(SETS, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=set_cols)
    for row in new_set_rows:
        w.writerow(row)
with open(REPS) as f:
    rep_cols = next(csv.reader(f))
with open(REPS, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rep_cols)
    for row in new_rep_rows:
        w.writerow(row)

print(f"appended {len(new_set_rows)} sets, {len(new_rep_rows)} rep_metric rows")
for sr in new_set_rows:
    print(f"  {sr['set_id']}: {sr['load_entered']}lb x{sr['actual_reps']}")
