#!/usr/bin/env python3
"""Derive per-lift ROM priors from the Vitruve ground-truth rows — DERIVED, never
hand-built (rep_metrics.csv already contains hundreds of measured ROMs).

    python dataset/tools/derive_rom_priors.py        # writes priors/{lift}_rom.csv

Output: one CSV per lift with n / median / q25 / q75 / lo / hi (cm), where lo/hi are
the 5th/95th percentiles — the ADVISORY plausibility band. Consumers flag reps
outside the band (e.g. `VideoConfig.rom_prior_cm`); they never gate on it
(learning #16's abstention rules: priors advise, measurements decide).
Re-run after ingesting new Vitruve sets; the prior sharpens as the DB grows.
"""
from __future__ import annotations
import os

import numpy as np
import pandas as pd

DATASET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    reps = pd.read_csv(os.path.join(DATASET, "rep_metrics.csv"))
    sets = pd.read_csv(os.path.join(DATASET, "sets.csv"))
    d = reps[(reps.vendor == "vitruve") & (reps.metric == "rom")
             & reps.rep_index.notna() & ~reps.flag.isin(["phantom", "missed"])]
    d = d.merge(sets[["set_id", "lift"]], on="set_id", how="left")
    d = d[d.value.notna() & (d.value > 0)]
    if d.empty:
        print("no Vitruve rom rows found")
        return 1
    for lift, g in d.groupby("lift"):
        cm = g.value.astype(float)        # canonical unit is cm (INGESTION.md)
        out = pd.DataFrame([{
            "lift": lift, "n_reps": len(cm), "n_sets": g.set_id.nunique(),
            "median_cm": round(float(cm.median()), 1),
            "q25_cm": round(float(cm.quantile(0.25)), 1),
            "q75_cm": round(float(cm.quantile(0.75)), 1),
            "lo_cm": round(float(cm.quantile(0.05)), 1),
            "hi_cm": round(float(cm.quantile(0.95)), 1),
            "source": "derived from vitruve rep_metrics (derive_rom_priors.py)",
        }])
        path = os.path.join(DATASET, "priors", f"{lift}_rom.csv")
        out.to_csv(path, index=False)
        print(f"{lift:<16} n={len(cm):>3} sets={g.set_id.nunique()} "
              f"median {out.median_cm[0]} cm  band [{out.lo_cm[0]}, {out.hi_cm[0]}] -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
