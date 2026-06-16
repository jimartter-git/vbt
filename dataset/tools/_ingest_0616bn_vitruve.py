"""Ingest the 2026-06-16 Bench Press Vitruve export into sets.csv + rep_metrics.csv.

5 sets x 10 clean reps (Vitruve is reliable for the vertical lifts; `# Rep.` is
1-based and clean -> use directly as true_rep). Set 1 is a heavier top set
(102.1 kg / 225 lb), sets 2-5 are back-offs at 93.0 kg / 205 lb. Each set also has
an Apple Watch IMU file (dataset/raw/20260616-BN-N_watch.csv) and an HD video in R2
(20260616-BN_N.mov). RPE not provided by the lifter -> left blank.
"""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "dataset", "raw", "20260616-BN_vitruve.csv")
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

# lifter-entered load in lb (102.09 kg = 225 lb, 93.01 kg = 205 lb)
LB = {"1": 225, "2": 205, "3": 205, "4": 205, "5": 205}

new_set_rows, new_rep_rows = [], []
for s in sorted(by_set, key=int):
    reps = by_set[s]
    sid = f"20260616-BN-{s}"
    load_kg = round(float(reps[0]["Weight (kg)"]), 1)
    note = ("Bench Press, 2026-06-16. Vitruve GT (reliable for the vertical lifts; "
            "clean per-rep export). " + (
                "Heavier top set (225 lb). " if s == "1" else "Back-off set (205 lb). ") +
            f"Apple Watch IMU in dataset/raw/20260616-BN-{s}_watch.csv; "
            f"HD video 20260616-BN_{s}.mov in R2. SmartBarbell pending.")
    new_set_rows.append(dict(set_id=sid, date="2026-06-16", lift="bench",
                             load_kg=load_kg, load_entered=LB[s], load_unit="lb",
                             set_index=s, target_reps="", actual_reps=len(reps),
                             rpe_actual="", notes=note))
    for r in reps:
        rep = int(r["# Rep."])                       # 1-based, clean -> true_rep = rep_index
        for col, metric, unit, fn in MET:
            v = r.get(col, "").strip()
            if v == "":
                continue
            new_rep_rows.append(dict(set_id=sid, vendor="vitruve", rep_index=rep, true_rep=rep,
                                     metric=metric, value=fn(v), unit=unit, flag="", confidence=""))

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
