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

    per_rep = d.copy()
    # Aligned rows REQUIRE a physical rep number (true_rep). Per-rep rows that
    # lack it (e.g. a vendor that mis-counted reps) can't be aligned across
    # vendors -> reported separately, never positionally forced onto rep_index.
    unaligned = per_rep[per_rep["true_rep"].isna() & per_rep["rep_index"].notna()]
    aligned = per_rep[per_rep["true_rep"].notna()].copy()
    aligned["rep"] = aligned["true_rep"].astype(int)

    # Flags that mean "not a real measurement" — keep them out of the numbers.
    INVALID = {"phantom", "missed"}
    flagged = aligned[aligned.flag.notna() & (aligned.flag != "")]
    valid = aligned[~aligned.flag.isin(INVALID)]
    table = valid.pivot_table(index="rep", columns="vendor",
                              values="value", aggfunc="first").sort_index()

    print(f"\nPer-rep {args.metric} (rows = physical rep / true_rep):")
    print(table.to_string(na_rep="  -"))
    if not flagged.empty:
        notes = ", ".join(
            f"{r.vendor} rep{int(r.rep)}={r.flag} "
            f"({'excluded' if r.flag in INVALID else 'kept, annotated'})"
            for _, r in flagged.iterrows())
        print(f"  flagged: {notes}")
    if not unaligned.empty:
        for v, g in unaligned.groupby("vendor"):
            fl = [x for x in g.flag.dropna().unique() if x]
            tag = f" [{fl[0]}]" if fl else ""
            print(f"  unaligned: {v} reported {len(g)} reps{tag}, true_rep unresolved "
                  f"(mean {g.value.mean():.3f}) — excluded from alignment")

    # Per-vendor summary. VL is best-referenced and labels WHICH rep it runs to,
    # so a 7-rep vendor's loss is never silently equated with an 8-rep vendor's.
    print("\nPer-vendor summary (VL = best rep -> that vendor's last rep):")
    summary = []
    for v in table.columns:
        col = table[v].dropna()
        last = int(col.index.max())
        summary.append((v, len(col), round(col.mean(), 3), round(col.max(), 3),
                        last, round(velocity_loss(col), 1)))
    sm = pd.DataFrame(summary, columns=["vendor", "n_reps", "mean", "best", "last_rep", "VL%"]).set_index("vendor")
    print(sm.to_string())

    # Apples-to-apples: velocity loss over the reps EVERY vendor observed.
    if len(table.columns) > 1:
        common = sorted(set.intersection(*[set(table[v].dropna().index) for v in table.columns]))
        if len(common) >= 2:
            lo, hi = common[0], common[-1]
            print(f"\nCommon-window VL (best -> rep {hi}, using reps {common} present for all vendors):")
            cw = []
            for v in table.columns:
                col = table[v].loc[common]
                best = col.max()
                vl = (best - col.loc[hi]) / best * 100 if best > 0 else float("nan")
                cw.append((v, round(vl, 1)))
            print(pd.DataFrame(cw, columns=["vendor", "VL%"]).set_index("vendor").to_string())

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
