"""Ingest the 2026-06-18 Incline Bench Vitruve export into sets.csv + rep_metrics.csv.

3 sets x 10 clean reps, ascending load 165/175/185 lb (74.86/79.40/83.94 kg). Vitruve is
reliable on the vertical lifts; `# Rep.` is 1-based and clean -> use as true_rep. Each set
has an Apple Watch IMU file (20260618-IB-N_watch.csv) and an HD video in R2
(20260618-IB-N.mov). RPE not provided -> blank. No SmartBarbell for this session.
"""
import csv, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "dataset", "raw", "20260618-IB_vitruve.csv")
SETS = os.path.join(REPO, "dataset", "sets.csv")
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")

MET = [
    ("Mean Velocity (m/s)", "mean_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Mean Propulsive Velocity (m/s)", "mean_propulsive_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Peak Velocity (m/s)", "peak_velocity", "m/s", lambda x: round(float(x), 3)),
    ("ROM (Range of Motion) (m)", "rom", "cm", lambda x: round(float(x) * 100, 1)),
    ("Mean Power [MV] (W)", "mean_power", "W", lambda x: round(float(x), 2)),
    ("Peak Power (W)", "peak_power", "W", lambda x: round(float(x), 2)),
    ("Time to Peak Velocity (ms)", "time_to_peak", "s", lambda x: round(float(x) / 1000, 3)),
]
LB = {"1": 165, "2": 175, "3": 185}    # lifter-entered load (ascending)

rows = list(csv.DictReader(open(SRC)))
by_set = {}
for r in rows:
    by_set.setdefault(r["# Set"].strip(), []).append(r)

new_set_rows, new_rep_rows = [], []
for s in sorted(by_set, key=int):
    reps = by_set[s]
    sid = f"20260618-IB-{s}"
    load_kg = round(float(reps[0]["Weight (kg)"]), 1)
    note = (f"Incline Barbell Bench Press, 2026-06-18, ascending load ({LB[s]} lb). "
            f"Vitruve GT (clean per-rep). Apple Watch IMU in dataset/raw/{sid}_watch.csv; "
            f"HD video {sid}.mov in R2. No SmartBarbell this session.")
    new_set_rows.append(dict(set_id=sid, date="2026-06-18", lift="incline_bench",
                             load_kg=load_kg, load_entered=LB[s], load_unit="lb",
                             set_index=s, target_reps="", actual_reps=len(reps),
                             rpe_actual="", notes=note))
    for r in reps:
        rep = int(r["# Rep."])
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
