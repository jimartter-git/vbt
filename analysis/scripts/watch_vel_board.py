#!/usr/bin/env python3
"""Watch VELOCITY-accuracy board — the new wave-segmenter ZUPT velocity vs Vitruve.

We had counts (wave_eval: 13/15) but only per-lift BIAS for velocity. This board reports
the accuracy we actually care about — per-rep RMSE + Pearson r + bias — against the
project target (r > 0.95, SEE < 0.07 m/s; Achermann hit r > 0.97).

ONE pinned MV definition: mean concentric velocity = mean |v| over the ZUPT-anchored
bottom→top window (= ROM/concentric-duration, the LPT/Vitruve definition). The ZUPT
velocity is integrated from raw accel with zero-velocity at the wave's true turnarounds —
NOT the high-pass-distorted bootstrap displacement (that wave only LOCATES the
turnarounds). Reps are aligned positionally; on a count mismatch we align the first
min(N,M) and flag it (an honest, not silent, comparison).

    python analysis/scripts/watch_vel_board.py
"""
from __future__ import annotations
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_analysis.ingest import load_session            # noqa: E402
from vbt_analysis.velocity import vertical_acceleration  # noqa: E402
from vbt_analysis import wave_segment as ws              # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS_CSV = os.path.join(REPO, "dataset", "rep_metrics.csv")

# Single source of truth for watch sessions = wave_eval.SESSIONS (learning #30: don't
# hand-maintain a second registry that silently drifts). Lift code = the set_id's middle
# token. New watch sessions register once, in wave_eval, and appear on both boards.
from wave_eval import SESSIONS as _WATCH_CSVS  # noqa: E402
SESSIONS = {sid: sid.split("-")[1] for sid in _WATCH_CSVS}
TARGET_R, TARGET_SEE = 0.95, 0.07


def vit(sid, metric="mean_velocity"):
    return [float(r["value"]) for r in csv.DictReader(open(REPS_CSV))
            if r["set_id"] == sid and r["vendor"] == "vitruve"
            and r["metric"] == metric and (r["rep_index"] or "").strip()
            and (r["flag"] or "") != "phantom"]


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main():
    print("\nWATCH VELOCITY board — wave-segmenter ZUPT MV vs Vitruve "
          f"(target r>{TARGET_R}, SEE<{TARGET_SEE})\n")
    hdr = (f"{'session':<16}{'lift':>5}{'n':>4}{'GT':>4}{'rmse':>7}{'rmseC':>7}{'r':>7}"
           f"{'bias':>7}  note")
    print(hdr); print("-" * len(hdr))
    bylift = {}            # lift -> (all source MV, all ref MV) pooled per-rep
    for sid, lift in SESSIONS.items():
        df = load_session(os.path.join(REPO, "dataset", "raw", f"{sid}_watch.csv"))
        t = df["t"].to_numpy(float)
        res = ws.segment(t, vertical_acceleration(df))
        mv = [r.mean_concentric_velocity for r in res.reps]
        vmv = vit(sid)
        gt = len(vmv)
        k = min(len(mv), len(vmv))
        note = "" if len(mv) == gt else f"count {len(mv)}≠{gt}; first {k} aligned"
        s, r = np.array(mv[:k]), np.array(vmv[:k])
        rmse = float(np.sqrt(np.mean((s - r) ** 2))) if k else float("nan")
        bias = float(np.mean(s - r)) if k else float("nan")
        rmse_c = float(np.std(s - r)) if k else float("nan")    # after constant-offset calib
        rr = pearson(s, r)
        bylift.setdefault(lift, [[], []])
        bylift[lift][0].extend(s.tolist()); bylift[lift][1].extend(r.tolist())
        print(f"{sid:<16}{lift:>5}{len(mv):>4}{gt:>4}{rmse:>7.3f}{rmse_c:>7.3f}"
              f"{(rr if rr == rr else float('nan')):>7.2f}{bias:>+7.3f}  {note}")

    print("\nPer-lift (per-rep pooled). rmseC = RMSE after a per-lift CONSTANT-offset "
          "calibration (learning #4):")
    print(f"  {'lift':<5}{'reps':>5}{'rmse':>8}{'rmseC':>8}{'r':>7}{'bias':>8}{'  calib vs SEE':>15}")
    alls, allr = [], []
    for lift, (s, r) in bylift.items():
        s, r = np.array(s), np.array(r)
        rmse = float(np.sqrt(np.mean((s - r) ** 2)))
        rmse_c = float(np.std(s - r))
        rr = pearson(s, r); bias = float(np.mean(s - r))
        alls.extend(s.tolist()); allr.extend(r.tolist())
        ok = "✓" if rmse_c < TARGET_SEE else "✗"
        print(f"  {lift:<5}{len(s):>5}{rmse:>8.3f}{rmse_c:>8.3f}{rr:>7.2f}{bias:>+8.3f}{ok:>10}")
    alls, allr = np.array(alls), np.array(allr)
    rmse = float(np.sqrt(np.mean((alls - allr) ** 2)))
    # bias-corrected per lift, then pooled (each lift gets its own calibration)
    resid = []
    for lift, (s, r) in bylift.items():
        s, r = np.array(s), np.array(r)
        resid.extend((s - r - np.mean(s - r)).tolist())
    rmse_c = float(np.std(resid))
    print(f"\nOVERALL per-rep: n={len(alls)}  RMSE={rmse:.3f}  r={pearson(alls, allr):.2f}  "
          f"bias={np.mean(alls - allr):+.3f}")
    print(f"OVERALL after per-lift calibration: RMSE_calibrated={rmse_c:.3f}  "
          f"(target SEE<{TARGET_SEE})")
    print("\nNotes: (1) error is dominated by a CONSTANT per-lift offset (wrist vs bar, "
          "learning #4) — rmseC is the shippable accuracy after calibration. (2) a 10-rep "
          "slow lift caps Pearson r statistically (narrow MV range, learning #25).")


if __name__ == "__main__":
    main()
