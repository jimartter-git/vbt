"""Canonical cross-source metric definitions.

THE one velocity-loss definition for the whole project. Before this module there
were four divergent formulas (vel_eval best→mean-last-2, dataset compare.py
best→last-rep, vbt_analysis.velocity best→min, Swift SetSummary best→min) — so
"loss" numbers were silently incomparable across tools. All four now use THIS
definition; Swift `SetSummary` mirrors it (lock-step note below) — do NOT
"correct" Swift back to best→min. Dataset rules
(dataset/README.md): reference the BEST rep (not rep 1 — warm-in makes rep 2–3
fastest), run to the TERMINAL window (never best→min: a mid-set slow rep must not
inflate loss past the set's end), and STATE the window.

Definition:  VL% = (best − terminal) / best × 100
  best     = max of the usable per-rep mean velocities
  terminal = mean of the last `terminal_k` usable values (k=2 default: robust to
             single terminal-rep noise — the terminal rep is the least reliably
             measured rep in the set, by every source)

`flags` (optional, parallel to `values`) excludes non-measurements from BOTH ends:
phantom/missed rows are not reps. `exclude_partial` optionally also drops
`partial_rom` reps from the terminal window — measured on the 2026-06-11 velocity
board it changed loss error by <0.2pp (noise-level) and makes our treatment
asymmetric vs ground truth (Vitruve rows carry no partial flags), so it defaults
OFF; the knob stays for sources whose partials are known artifacts. The k=2
terminal window beat k=1 decisively on the same board (lift-weighted |err|
3.97 vs 5.57pp), confirming the default.

Keep in lock-step with `SetSummary.velocityLossPct` in
Packages/VBTCore/Sources/VBTCore/VelocitySource.swift and docs/data-schema.md.
"""
from __future__ import annotations

import numpy as np

# Flags that mean "not a real measurement" — never usable (same set as compare.py).
INVALID_FLAGS = {"phantom", "missed"}


def velocity_loss_pct(values, flags=None, terminal_k: int = 2,
                      exclude_partial: bool = False) -> float:
    """Canonical intra-set velocity loss (%), best rep → terminal window.

    `values`: per-rep mean velocities in physical rep order. `flags`: optional
    parallel flag strings ('' / None for clean reps). Returns NaN when fewer than
    3 usable reps (a 2-rep "loss" is noise, and sources that captured <3 reps
    aren't comparable).
    """
    vals = list(values)
    fl = list(flags) if flags is not None else [None] * len(vals)
    usable = [(v, f) for v, f in zip(vals, fl)
              if v is not None and v == v and (f or "") not in INVALID_FLAGS]
    if len(usable) < 3:
        return float("nan")
    best = max(v for v, _ in usable)
    if best <= 0:
        return float("nan")
    window = [(v, f) for v, f in usable]
    if exclude_partial:
        non_partial = [(v, f) for v, f in window if (f or "") != "partial_rom"]
        if len(non_partial) >= 3:           # never exclude below the validity floor
            window = non_partial
    k = max(1, min(terminal_k, len(window) - 1))   # terminal can't swallow the best rep
    terminal = float(np.mean([v for v, _ in window[-k:]]))
    return (best - terminal) / best * 100.0


def loss_window_label(n_reps: int, terminal_k: int = 2) -> str:
    """Human label for WHICH reps a loss ran to — dataset rule: state the window."""
    k = max(1, min(terminal_k, n_reps - 1))
    if k == 1:
        return f"best→rep{n_reps}"
    return f"best→mean(rep{n_reps - k + 1}–{n_reps})"
