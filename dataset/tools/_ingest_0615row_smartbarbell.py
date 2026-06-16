"""Ingest 2026-06-15 barbell-row SmartBarbell screenshots (5 sets) into rep_metrics.csv.

SB columns: Ascent(s)=concentric_time, Descent(s)=eccentric_time, Pause(s)=pause_time,
Velocity(m/s)=mean_velocity, ROM(m)->cm, Shift(m)->cm. SB is a VIDEO/CV app (plate
bounding-box), so its errors are video errors. Counts: 9/9/10/8/8 vs the true 10s ->
under-counts 4 of 5 sets. Per INGESTION.md: matched-count set (3) maps true_rep 1:1;
under-count sets get true_rep BLANK + flag=undercount (count-only, not masquerading).
SB set 1 starts at 0.71 (not the ~0.63 warmup pace) -> it did NOT capture the 2 warmup
reps Vitruve logged; it just missed 1 of the 10 working reps.
"""
import csv, os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")

# per set: list of (Ascent, Descent, Pause, Velocity, ROM_m, Shift_m)
SB = {
    1: [(0.70,0.90,0.00,0.71,0.50,0.02),(0.57,0.90,0.00,0.80,0.45,0.03),(0.70,0.70,0.00,0.69,0.48,0.02),
        (0.63,0.70,0.00,0.75,0.48,0.03),(0.67,0.70,0.00,0.73,0.49,0.03),(0.70,0.70,0.00,0.69,0.48,0.01),
        (0.70,0.73,0.00,0.71,0.50,0.03),(0.70,0.83,0.00,0.69,0.49,0.02),(0.90,0.80,0.00,0.57,0.52,0.04)],
    2: [(0.53,0.93,0.00,0.79,0.42,0.01),(0.70,0.80,0.00,0.69,0.48,0.02),(0.70,0.75,0.00,0.68,0.48,0.02),
        (0.53,0.90,0.00,0.83,0.44,0.01),(0.70,0.77,0.00,0.72,0.50,0.02),(0.70,0.77,0.00,0.69,0.49,0.02),
        (0.77,0.83,0.00,0.67,0.51,0.02),(0.80,0.90,0.00,0.61,0.49,0.02),(0.73,1.07,0.00,0.68,0.50,0.03)],
    3: [(1.03,0.63,0.00,0.54,0.54,0.05),(0.57,0.60,0.00,0.87,0.49,0.03),(0.57,0.57,0.00,0.84,0.48,0.01),
        (0.53,0.60,0.00,0.95,0.51,0.02),(0.53,0.60,0.00,0.90,0.48,0.02),(0.53,0.60,0.00,0.94,0.50,0.02),
        (0.53,0.63,0.00,0.91,0.49,0.02),(0.63,0.27,0.00,0.83,0.52,0.03),(0.60,0.63,0.00,0.87,0.52,0.03),
        (0.67,0.67,0.00,0.79,0.52,0.02)],
    4: [(0.73,0.83,0.00,0.68,0.50,0.02),(0.70,0.77,0.00,0.70,0.49,0.02),(0.77,0.80,0.00,0.68,0.52,0.03),
        (0.70,0.90,0.00,0.71,0.50,0.02),(0.50,1.03,0.00,0.83,0.41,0.03),(0.80,1.03,0.00,0.63,0.51,0.03),
        (0.63,1.17,0.00,0.73,0.46,0.03),(0.73,1.10,0.00,0.70,0.51,0.03)],
    5: [(0.63,0.73,0.00,0.70,0.44,0.02),(0.60,0.73,0.00,0.78,0.47,0.02),(0.67,0.70,0.00,0.73,0.49,0.01),
        (0.67,0.67,0.00,0.74,0.49,0.02),(0.50,0.80,0.00,0.82,0.41,0.02),(0.60,0.83,0.00,0.75,0.45,0.01),
        (0.70,1.27,0.00,0.73,0.51,0.01),(0.80,0.87,0.37,0.63,0.50,0.01)],
}
MATCHED = {3}                              # SB count == Vitruve count -> 1:1 true_rep

rows = []
for s, reps in SB.items():
    sid = f"20260615-ROW-{s}"
    flag = "" if s in MATCHED else "undercount"
    for i, (asc, desc, pause, vel, rom_m, shift_m) in enumerate(reps, 1):
        tr = i if s in MATCHED else ""     # blank true_rep for under-count sets
        out = [("mean_velocity", vel, "m/s"), ("rom", round(rom_m*100), "cm"),
               ("shift", round(shift_m*100), "cm"), ("concentric_time", asc, "s"),
               ("eccentric_time", desc, "s"), ("pause_time", pause, "s")]
        for metric, value, unit in out:
            rows.append(dict(set_id=sid, vendor="smartbarbell", rep_index=i, true_rep=tr,
                             metric=metric, value=value, unit=unit, flag=flag, confidence=""))

with open(REPS) as f:
    cols = next(csv.reader(f))
with open(REPS, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    for r in rows:
        w.writerow(r)
print(f"appended {len(rows)} SmartBarbell rep_metric rows across {len(SB)} sets")
for s, reps in SB.items():
    mv = [r[3] for r in reps]
    print(f"  ROW-{s}: SB {len(reps)} reps, mean MV {sum(mv)/len(mv):.3f}"
          f"{' (1:1 vs Vitruve)' if s in MATCHED else ' (undercount, true_rep blank)'}")
