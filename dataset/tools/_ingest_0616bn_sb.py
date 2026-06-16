"""Ingest the 2026-06-16 bench SmartBarbell exports (5 sets) into rep_metrics.csv.

SmartBarbell is a VIDEO/CV app (INGESTION.md) — the CV competitor. All 5 sets show 10
reps, MATCHING Vitruve's count (no phantom/undercount rows) -> true_rep = rep_index 1:1.
Column map (INGESTION.md): Velocity->mean_velocity, ROM->rom (m->cm), Ascent->concentric_time,
Descent->eccentric_time, Pause->pause_time, Shift->shift (m->cm).
Gym: Westwood Athletics (Richmond VA, performance gym). Rogue DEEP-DISH plates: set 1 = 2x45;
sets 2-5 = a 10 + 25 in front of a single deep-dish 45 (front-most plate facing the camera is
the small one) — relevant to the px->m scale, less so to the velocity SB reports here.
"""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")

# transcribed (rep: ascent, descent, pause, velocity, rom_m, shift_m)
SB = {
 1: [(0.90,1.43,0.00,0.41,0.37,0.08),(0.80,0.83,0.00,0.43,0.35,0.08),(0.80,0.90,0.00,0.41,0.32,0.08),
     (0.83,0.83,0.00,0.38,0.32,0.06),(0.87,0.73,0.00,0.37,0.32,0.06),(0.90,0.83,0.00,0.37,0.33,0.08),
     (1.03,0.80,0.00,0.30,0.32,0.08),(0.97,0.93,0.00,0.33,0.32,0.08),(1.17,0.93,0.00,0.27,0.31,0.08),
     (1.47,1.27,0.00,0.23,0.33,0.05)],
 2: [(0.93,1.33,0.23,0.38,0.36,0.09),(0.73,0.87,0.00,0.48,0.35,0.04),(0.77,0.73,0.00,0.44,0.34,0.07),
     (0.83,0.67,0.00,0.41,0.34,0.06),(0.80,0.63,0.00,0.44,0.35,0.06),(0.80,0.60,0.00,0.43,0.35,0.06),
     (0.83,0.67,0.00,0.41,0.34,0.08),(0.90,0.63,0.00,0.39,0.33,0.06),(1.00,0.67,0.00,0.34,0.34,0.07),
     (1.10,2.13,0.00,0.31,0.33,0.05)],
 3: [(0.87,1.70,0.00,0.40,0.35,0.11),(0.73,0.80,0.00,0.47,0.34,0.07),(0.70,0.70,0.00,0.47,0.33,0.06),
     (0.73,0.63,0.00,0.44,0.32,0.06),(0.77,0.63,0.00,0.42,0.32,0.08),(0.87,0.73,0.00,0.40,0.36,0.08),
     (0.90,0.70,0.00,0.36,0.32,0.08),(1.00,0.80,0.00,0.32,0.33,0.05),(0.97,0.83,0.00,0.34,0.33,0.06),
     (1.63,1.67,0.00,0.21,0.34,0.06)],
 4: [(0.97,1.40,0.00,0.34,0.33,0.08),(0.73,0.87,0.00,0.44,0.32,0.06),(0.83,0.67,0.00,0.41,0.34,0.06),
     (0.83,0.70,0.00,0.40,0.33,0.06),(1.00,0.70,0.00,0.32,0.32,0.07),(0.93,0.83,0.00,0.35,0.33,0.06),
     (1.03,0.80,0.00,0.30,0.31,0.07),(1.20,0.90,0.00,0.26,0.33,0.06),(1.13,1.10,0.00,0.26,0.30,0.08),
     (1.40,1.10,0.00,0.23,0.32,0.06)],
 5: [(1.17,1.30,0.17,0.30,0.33,0.07),(0.77,1.07,0.00,0.43,0.33,0.09),(0.83,0.63,0.00,0.41,0.34,0.07),
     (0.80,0.67,0.00,0.42,0.34,0.07),(1.03,0.67,0.00,0.34,0.36,0.07),(1.20,0.90,0.00,0.26,0.31,0.06),
     (1.23,0.97,0.00,0.25,0.31,0.06),(1.60,1.00,0.00,0.20,0.31,0.06),(1.37,0.83,0.00,0.24,0.33,0.06),
     (2.67,1.13,0.00,0.13,0.32,0.06)],
}

new = []
def add(sid, rep, metric, val, unit):
    new.append(dict(set_id=sid, vendor="smartbarbell", rep_index=rep, true_rep=rep,
                    metric=metric, value=val, unit=unit, flag="", confidence=""))

for s, reps in SB.items():
    sid = f"20260616-BN-{s}"
    for i, (asc, desc, pause, vel, rom, shift) in enumerate(reps, 1):
        add(sid, i, "mean_velocity", vel, "m/s")
        add(sid, i, "rom", round(rom * 100, 1), "cm")
        add(sid, i, "concentric_time", asc, "s")
        add(sid, i, "eccentric_time", desc, "s")
        if pause > 0:
            add(sid, i, "pause_time", pause, "s")
        add(sid, i, "shift", round(shift * 100, 1), "cm")

with open(REPS) as f:
    cols = next(csv.reader(f))
with open(REPS, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    for r in new:
        w.writerow(r)
print(f"appended {len(new)} SmartBarbell rep_metric rows across {len(SB)} sets (10 reps each)")
