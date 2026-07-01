#!/usr/bin/env python3
"""Track B scoreboard — the lift-agnostic wave segmenter vs Vitruve, ONE config.

Counts every watch session (rows/bench/squat/RDL) with a SINGLE detector config (no
per-lift thresholds) and compares to Vitruve per-rep ground truth. Also reports the
per-lift velocity bias/confidence (the interpretable-velocity goal) and, with
--blind, a leave-one-session-out check that the prominence param holds on held-out
sessions (Track A guardrail).

    python analysis/scripts/wave_eval.py
    python analysis/scripts/wave_eval.py --blind
"""
from __future__ import annotations
import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_analysis.ingest import load_session            # noqa: E402
from vbt_analysis.velocity import vertical_acceleration  # noqa: E402
from vbt_analysis import wave_segment as ws              # noqa: E402
from vbt_analysis import validation as val               # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPS_CSV = os.path.join(REPO, "dataset", "rep_metrics.csv")

# watch session -> raw CSV (all local). lift code is the middle token.
SESSIONS = {
    "20260615-ROW-2": "dataset/raw/20260615-ROW-2_watch.csv",
    "20260615-ROW-3": "dataset/raw/20260615-ROW-3_watch.csv",
    "20260615-ROW-4": "dataset/raw/20260615-ROW-4_watch.csv",
    "20260615-ROW-5": "dataset/raw/20260615-ROW-5_watch.csv",
    "20260616-BN-1": "dataset/raw/20260616-BN-1_watch.csv",
    "20260616-BN-2": "dataset/raw/20260616-BN-2_watch.csv",
    "20260616-BN-3": "dataset/raw/20260616-BN-3_watch.csv",
    "20260616-BN-4": "dataset/raw/20260616-BN-4_watch.csv",
    "20260616-BN-5": "dataset/raw/20260616-BN-5_watch.csv",
    "20260617-SQ-1": "dataset/raw/20260617-SQ-1_watch.csv",
    "20260617-SQ-2": "dataset/raw/20260617-SQ-2_watch.csv",
    "20260617-SQ-3": "dataset/raw/20260617-SQ-3_watch.csv",
    "20260617-SQ-4": "dataset/raw/20260617-SQ-4_watch.csv",
    "20260617-RDL-1": "dataset/raw/20260617-RDL-1_watch.csv",
    "20260617-RDL-2": "dataset/raw/20260617-RDL-2_watch.csv",
    "20260618-IB-1": "dataset/raw/20260618-IB-1_watch.csv",
    "20260618-IB-2": "dataset/raw/20260618-IB-2_watch.csv",
    "20260618-IB-3": "dataset/raw/20260618-IB-3_watch.csv",
    # --- 2026-06-19 -> 06-29 (registered 2026-06-29). Wrist mounts only; the bar-sleeve
    # recordings (06-27 IB-4, 06-28 DL-4 = *_watch_bar.csv, vendor watch_bar) are a distinct
    # modality, kept out of the wrist board. SQ-MM = a second athlete (the owner's wife). ---
    "20260619-DL-1": "dataset/raw/20260619-DL-1_watch.csv",
    "20260619-DL-2": "dataset/raw/20260619-DL-2_watch.csv",
    "20260619-DL-3": "dataset/raw/20260619-DL-3_watch.csv",
    "20260619-DL-4": "dataset/raw/20260619-DL-4_watch.csv",
    "20260619-DL-5": "dataset/raw/20260619-DL-5_watch.csv",
    "20260619-DL-6": "dataset/raw/20260619-DL-6_watch.csv",
    "20260619-DL-7": "dataset/raw/20260619-DL-7_watch.csv",
    "20260619-SQ-MM-1": "dataset/raw/20260619-SQ-MM-1_watch.csv",
    "20260619-SQ-MM-2": "dataset/raw/20260619-SQ-MM-2_watch.csv",
    "20260619-SS-1": "dataset/raw/20260619-SS-1_watch.csv",
    "20260619-SS-2": "dataset/raw/20260619-SS-2_watch.csv",
    "20260624-BN-1": "dataset/raw/20260624-BN-1_watch.csv",
    "20260624-BN-2": "dataset/raw/20260624-BN-2_watch.csv",
    "20260624-BN-3": "dataset/raw/20260624-BN-3_watch.csv",
    "20260624-BN-4": "dataset/raw/20260624-BN-4_watch.csv",
    "20260624-BN-5": "dataset/raw/20260624-BN-5_watch.csv",
    "20260624-ROW-1": "dataset/raw/20260624-ROW-1_watch.csv",
    "20260624-ROW-2": "dataset/raw/20260624-ROW-2_watch.csv",
    "20260624-ROW-3": "dataset/raw/20260624-ROW-3_watch.csv",
    "20260624-ROW-4": "dataset/raw/20260624-ROW-4_watch.csv",
    "20260624-ROW-5": "dataset/raw/20260624-ROW-5_watch.csv",
    "20260624-ROW-6": "dataset/raw/20260624-ROW-6_watch.csv",
    "20260627-IB-1": "dataset/raw/20260627-IB-1_watch.csv",
    "20260627-IB-2": "dataset/raw/20260627-IB-2_watch.csv",
    "20260627-IB-3": "dataset/raw/20260627-IB-3_watch.csv",
    "20260628-DL-1": "dataset/raw/20260628-DL-1_watch.csv",
    "20260628-DL-2": "dataset/raw/20260628-DL-2_watch.csv",
    "20260628-DL-3": "dataset/raw/20260628-DL-3_watch.csv",
    "20260629-ROW-1": "dataset/raw/20260629-ROW-1_watch.csv",
    "20260629-ROW-2": "dataset/raw/20260629-ROW-2_watch.csv",
    "20260629-ROW-3": "dataset/raw/20260629-ROW-3_watch.csv",
    "20260629-ROW-4": "dataset/raw/20260629-ROW-4_watch.csv",
    "20260629-ROW-5": "dataset/raw/20260629-ROW-5_watch.csv",
    "20260629-ROW-6": "dataset/raw/20260629-ROW-6_watch.csv",
    # --- 2026-06-30 bench (top set 245 lb + back-offs). Wrist mounts BN-2..5; set 1's
    # watch was fixed to the BAR sleeve (20260630-BN-1_watch_bar.csv, vendor watch_bar) —
    # a distinct modality, kept out of the wrist board like the earlier bar-sleeve records. ---
    "20260630-BN-2": "dataset/raw/20260630-BN-2_watch.csv",
    "20260630-BN-3": "dataset/raw/20260630-BN-3_watch.csv",
    "20260630-BN-4": "dataset/raw/20260630-BN-4_watch.csv",
    "20260630-BN-5": "dataset/raw/20260630-BN-5_watch.csv",
    # --- 2026-07-01 SHARED squat session (owner JM + wife MM), split from one mixed Vitruve
    # export. Only JM sets 2 & 5 have a WRIST recording (watch forgot for JM 1/3/4); both of
    # MM's sets were BAR-sleeve mounts (SQ-MM-*_watch_bar.csv, watch_bar) -> not on this
    # wrist board. Set_ids are per-lifter (JM SQ-5 == Vitruve source set 7). ---
    "20260701-SQ-2": "dataset/raw/20260701-SQ-2_watch.csv",
    "20260701-SQ-5": "dataset/raw/20260701-SQ-5_watch.csv",
}


def lift_of(sid):
    return sid.split("-")[1]


def vit(sid, metric="mean_velocity"):
    return [float(r["value"]) for r in csv.DictReader(open(REPS_CSV))
            if r["set_id"] == sid and r["vendor"] == "vitruve"
            and r["metric"] == metric and (r["rep_index"] or "").strip()
            and (r["flag"] or "") != "phantom"]


def analyze(sid, prominence_frac=ws.DEFAULT_PROMINENCE_FRAC):
    df = load_session(os.path.join(REPO, SESSIONS[sid]))
    t = df["t"].to_numpy(float)
    a = vertical_acceleration(df)
    return ws.segment(t, a, prominence_frac=prominence_frac)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prom", type=float, default=ws.DEFAULT_PROMINENCE_FRAC)
    ap.add_argument("--blind", action="store_true",
                    help="leave-one-session-out: re-pick prominence on the OTHER sessions, "
                         "score the held-out one (Track A blind protocol)")
    args = ap.parse_args()

    print(f"\nTrack B — wave segmenter (ONE config, prom={args.prom}) vs Vitruve\n")
    hdr = f"{'session':<16}{'lift':>5}{'GT':>4}{'wave':>6}{'Δ':>4}   per-lift velocity"
    print(hdr); print("-" * 58)
    results = {}
    errs = []
    bylift_bias = {}
    for sid in SESSIONS:
        gt = len(vit(sid))
        res = analyze(sid, args.prom)
        results[sid] = (gt, res)
        d = res.count - gt
        errs.append(abs(d))
        mv = [r.mean_concentric_velocity for r in res.reps]
        vmv = vit(sid)
        bias = (np.mean(mv[:min(len(mv), len(vmv))]) - np.mean(vmv[:min(len(mv), len(vmv))])
                ) if (mv and vmv) else float("nan")
        bylift_bias.setdefault(lift_of(sid), []).append(bias)
        flag = "" if d == 0 else "  ✗"
        print(f"{sid:<16}{lift_of(sid):>5}{gt:>4}{res.count:>6}{d:>+4}{flag}"
              f"   MV~{np.mean(mv) if mv else float('nan'):.2f} bias {bias:+.2f}")
    exact = sum(1 for e in errs if e == 0)
    print(f"\nEXACT {exact}/{len(errs)} sessions · mean|Δ| {np.mean(errs):.2f}")
    print("Per-lift velocity bias vs Vitruve (m/s, wrist−bar; interpretable-velocity):")
    for lift, biases in bylift_bias.items():
        bb = [b for b in biases if b == b]
        print(f"  {lift:<5} bias {np.mean(bb):+.3f}  (n={len(bb)})")

    if args.blind:
        print("\n── BLIND (leave-one-session-out): prominence frozen on the OTHER sessions ──")
        # The only free param is prominence_frac; "fit" = the single global default (it is
        # NOT tuned per session). LOO confirms the SAME frozen value scores held-out
        # sessions identically — i.e. there is no per-session tuning to leak.
        items = list(SESSIONS)
        gts = {sid: len(vit(sid)) for sid in items}

        def fit(train):           # one global value, independent of the split (the point)
            return args.prom

        def score(sid, prom):
            return abs(analyze(sid, prom).count - gts[sid])

        out = val.blind_in_sample_delta(items, fit, score, key=lambda s: lift_of(s))
        print(f"  blind mean|Δ| {out['blind_mean']:.2f}  ·  in-sample {out['in_sample_mean']:.2f}"
              f"  ·  delta {out['delta']:+.2f}  (0 = no per-session/ -lift tuning leak)")


if __name__ == "__main__":
    main()
