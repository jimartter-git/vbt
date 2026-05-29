#!/usr/bin/env python3
"""Cross-vendor comparison for one set (the 4-app table, automated).

Reads the source-of-truth CSVs directly (no SQLite build needed).

Run:  python dataset/tools/compare.py 20260529-DL-1 [--metric mean_velocity] [--ref vitruve]
"""
from __future__ import annotations
import argparse
import os
import sys

import numpy as np
import pandas as pd

DATASET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Preference order for the "ground truth" reference when --ref not given.
REF_PREFERENCE = ["vitruve", "stance", "metric", "smartbarbell", "wl_analysis"]


def load():
    reps = pd.read_csv(os.path.join(DATASET, "rep_metrics.csv"))
    sets = pd.read_csv(os.path.join(DATASET, "sets.csv"))
    return reps, sets


def velocity_loss(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 2 or s.max() <= 0:
        return float("nan")
    return (s.max() - s.min()) / s.max() * 100.0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("set_id")
    p.add_argument("--metric", default="mean_velocity")
    p.add_argument("--ref", default=None, help="reference vendor for agreement stats")
    args = p.parse_args()

    reps, sets = load()
    srow = sets[sets.set_id == args.set_id]
    if srow.empty:
        print(f"set_id {args.set_id} not found in sets.csv")
        return 1
    srow = srow.iloc[0]
    print(f"\n{args.set_id}  |  {srow.lift}  {srow.load_entered}{srow.load_unit} "
          f"({srow.load_kg} kg)  |  {srow.actual_reps} reps"
          + (f"  |  RPE {srow.rpe_actual}" if pd.notna(srow.rpe_actual) else ""))

    d = reps[(reps.set_id == args.set_id) & (reps.metric == args.metric)]
    if d.empty:
        avail = sorted(reps[reps.set_id == args.set_id].metric.unique())
        print(f"no '{args.metric}' rows. Available metrics: {avail}")
        return 1

    per_rep = d[d.rep_index.notna()].copy()
    per_rep["rep_index"] = per_rep["rep_index"].astype(int)

    # Flags that mean "not a real measurement" — keep them out of the numbers.
    INVALID = {"phantom", "missed"}
    flagged = per_rep[per_rep.flag.notna() & (per_rep.flag != "")]
    valid = per_rep[~per_rep.flag.isin(INVALID)]
    table = valid.pivot_table(index="rep_index", columns="vendor",
                              values="value", aggfunc="first").sort_index()

    print(f"\nPer-rep {args.metric}:")
    print(table.to_string(na_rep="  -"))
    if not flagged.empty:
        notes = ", ".join(f"{r.vendor} rep{int(r.rep_index)}={r.flag} (excluded)"
                          for _, r in flagged.iterrows())
        print(f"  flagged: {notes}")

    # Per-vendor summary.
    print("\nPer-vendor summary:")
    summary = []
    for v in table.columns:
        col = table[v].dropna()
        summary.append((v, len(col), round(col.mean(), 3), round(col.max(), 3),
                        round(velocity_loss(col), 1)))
    sm = pd.DataFrame(summary, columns=["vendor", "n_reps", "mean", "best", "VL%"]).set_index("vendor")
    print(sm.to_string())

    # Agreement vs a reference vendor.
    ref = args.ref or next((v for v in REF_PREFERENCE if v in table.columns), None)
    if ref and ref in table.columns:
        print(f"\nAgreement vs reference = {ref} (overlapping reps):")
        rows = []
        for v in table.columns:
            if v == ref:
                continue
            both = pd.concat([table[ref], table[v]], axis=1).dropna()
            if len(both) < 1:
                continue
            diff = both[v] - both[ref]
            rows.append((v, len(both), round(diff.mean(), 3),
                         round(np.sqrt((diff ** 2).mean()), 3)))
        if rows:
            ag = pd.DataFrame(rows, columns=["vendor", "n", "bias", "rmse"]).set_index("vendor")
            print(ag.to_string())
        print("\n(bias = vendor - ref; +ve means vendor reads high. A roughly "
              "constant bias across vendors supports an offset calibration.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
