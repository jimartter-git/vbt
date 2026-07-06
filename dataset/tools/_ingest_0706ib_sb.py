"""Ingest the 2026-07-06 Incline Bench SmartBarbell exports (4 sets).

SmartBarbell is a VIDEO/CV app (INGESTION.md) — the CV competitor.
Sets 1-3 = 10 reps each; set 4 = AMRAP finisher (14 reps). Vitruve GT only
covers set 4 (183/185/185/185 ladder ends with a rep-out top set); SB is the
source of truth for velocity on sets 1-3.

Screenshot mapping (transcribed by hand):
  - IMG_6309 (6:19, Fast playback) -> set 1 @ 175 lb (fastest 1st-rep velocity,
    cleanest 10-peak Y-axis wave in the graph, lightest load)
  - IMG_6310 (6:21) -> set 2 @ 185 lb
  - IMG_6311 (6:21) -> set 3 @ 185 lb (more fatigue than set 2: rep-10 ascent
    1.43 vs 1.27, MV 0.29 vs 0.35)
  - IMG_6312 (6:22, reps 1-10) + IMG_6313 (6:22, reps 5-14) -> set 4 @ 185 lb,
    14-rep AMRAP. Overlapping reps 5-10 match byte-for-byte across the two
    screenshots; set-4 rep 1/14 = 0.51/0.14 vs Vitruve 0.51/0.17 confirms the
    mapping.

Column map (INGESTION.md): Velocity->mean_velocity, ROM->rom (m->cm),
Ascent->concentric_time, Descent->eccentric_time, Pause->pause_time,
Shift->shift (m->cm). All 4 sets show 10/10/10/14 reps with no phantom /
undercount trailing row -> true_rep = rep_index 1:1.

Idempotent: strips any existing smartbarbell rows for the produced set_ids
before appending.
"""
from __future__ import annotations

import csv
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")

# (ascent, descent, pause, velocity, rom_m, shift_m) per rep
SB = {
 1: [(0.77,1.33,0.00,0.55,0.42,0.05),(0.80,0.70,0.00,0.54,0.43,0.03),
     (0.87,0.63,0.00,0.50,0.43,0.05),(0.83,0.63,0.00,0.53,0.44,0.02),
     (0.87,0.60,0.00,0.48,0.42,0.03),(0.83,0.67,0.00,0.53,0.44,0.03),
     (0.97,0.63,0.00,0.45,0.44,0.05),(1.07,0.67,0.00,0.41,0.44,0.06),
     (0.97,0.83,0.00,0.45,0.44,0.07),(1.07,1.03,0.00,0.40,0.43,0.06)],
 2: [(0.80,0.90,0.00,0.53,0.42,0.07),(0.80,0.63,0.00,0.54,0.43,0.03),
     (0.87,0.67,0.00,0.49,0.42,0.03),(0.87,0.67,0.00,0.50,0.44,0.04),
     (0.90,0.67,0.00,0.48,0.43,0.06),(1.00,0.67,0.00,0.43,0.43,0.03),
     (1.17,0.67,0.00,0.38,0.44,0.07),(1.13,0.73,0.00,0.39,0.44,0.06),
     (1.03,1.23,0.00,0.42,0.43,0.08),(1.27,1.03,0.00,0.35,0.44,0.06)],
 3: [(0.80,0.90,0.00,0.52,0.42,0.06),(0.83,0.63,0.00,0.52,0.44,0.03),
     (0.87,0.70,0.00,0.50,0.43,0.05),(0.90,0.70,0.00,0.48,0.43,0.05),
     (1.00,0.67,0.00,0.44,0.44,0.05),(1.20,0.77,0.00,0.36,0.43,0.06),
     (1.10,1.00,0.00,0.40,0.43,0.06),(1.13,1.00,0.00,0.38,0.43,0.05),
     (1.27,0.93,0.00,0.34,0.43,0.07),(1.43,1.07,0.00,0.29,0.42,0.07)],
 4: [(0.80,1.10,0.00,0.51,0.41,0.06),(0.87,0.67,0.00,0.48,0.42,0.04),
     (0.83,0.67,0.00,0.50,0.42,0.06),(0.87,0.70,0.00,0.50,0.44,0.05),
     (0.87,0.70,0.00,0.48,0.42,0.05),(0.90,0.70,0.00,0.47,0.42,0.05),
     (1.03,0.70,0.00,0.40,0.42,0.05),(1.13,0.73,0.00,0.37,0.42,0.04),
     (1.07,1.03,0.00,0.40,0.42,0.06),(1.20,0.93,0.00,0.35,0.42,0.06),
     (1.23,1.27,0.00,0.34,0.42,0.07),(1.30,1.00,0.00,0.33,0.43,0.05),
     (1.63,1.07,0.00,0.26,0.42,0.04),(2.63,1.53,0.00,0.14,0.37,0.07)],
}


def main() -> int:
    made = {f"20260706-IB-{s}" for s in SB}
    with open(REPS, newline="") as f:
        rows = list(csv.reader(f))
    hdr, body = rows[0], [r for r in rows[1:]
                          if not (r and r[0] in made and r[1] == "smartbarbell")]

    new = []
    def add(sid, rep, metric, val, unit):
        new.append([sid, "smartbarbell", rep, rep, metric, val, unit, "", ""])

    for s, reps in SB.items():
        sid = f"20260706-IB-{s}"
        for i, (asc, desc, pause, vel, rom, shift) in enumerate(reps, 1):
            add(sid, i, "mean_velocity", vel, "m/s")
            add(sid, i, "rom", round(rom * 100, 1), "cm")
            add(sid, i, "concentric_time", asc, "s")
            add(sid, i, "eccentric_time", desc, "s")
            if pause > 0:
                add(sid, i, "pause_time", pause, "s")
            add(sid, i, "shift", round(shift * 100, 1), "cm")

    with open(REPS, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(body)
        w.writerows(new)
    total_reps = sum(len(v) for v in SB.values())
    print(f"ingested {len(new)} SB rep_metric rows across {len(SB)} sets "
          f"({total_reps} reps: {'/'.join(str(len(v)) for v in SB.values())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
