"""The generalization guardrail's shared instruments: input provenance + blind validation.

Why this exists (CLAUDE.md learning #26, docs/classical-foundation.md):
our headline CV/watch numbers were computed on the same clips/sessions that informed
the knobs, AND the CV headline consumed per-clip hand-registered seeds. Both inflate a
score past what a consumer app would see. This module makes the two honest:

  * `provenance(...)` tags every eval run by the INPUTS it consumed, so the harness can
    headline only the seed-free (truly blind) number and report tap/oracle runs
    separately and labeled.
  * `leave_one_out(...)` / `blind_in_sample_delta(...)` freeze parameters on a training
    split and score on data that did NOT inform them — the blind number, plus the gap to
    the in-sample number (how much we're leaning on tuning/oracle inputs).

Lightweight on purpose (numpy only, no cv2) so the watch (vbt_analysis) and CV
(vbt_video) harnesses share one instrument.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

# --- input provenance ---------------------------------------------------------
SEED_FREE = "seed-free"        # no per-clip input at all → the generalization score
SIMULATED_TAP = "simulated-tap"  # a registered tap/rim-confirm: a real UI surface, but
#                                   pre-found, so reported separately (not the headline)
ORACLE = "oracle"              # a registered known-good answer with no first-contact UI
#                                (manual crop band, per-clip plate/angle hint) — circular


def provenance(seed=None, rim_px=None, band=None, scale=None) -> str:
    """Classify an eval run by the inputs it consumed (most-circular wins).

    - ORACLE: a manual crop `band` or a per-clip `scale` (plate/angle/kind) hint — these
      have no clean first-contact product surface; using them to score generalization is
      circular (they were registered because a prior session found the answer).
    - SIMULATED_TAP: a `seed` (a user tap) or a `rim_px` (a plate-rim confirm). Both are
      genuine in-app surfaces (learnings #10, #18) — allowed, but pre-registered here, so
      labeled "simulated" and reported separately from the headline.
    - SEED_FREE: nothing per-clip. The only number that answers "does this generalize?"
    """
    if band is not None or scale is not None:
        return ORACLE
    if seed is not None or rim_px is not None:
        return SIMULATED_TAP
    return SEED_FREE


def is_blind(prov: str) -> bool:
    """Only seed-free runs count toward the generalization headline."""
    return prov == SEED_FREE


# --- blind / leave-one-out validation ----------------------------------------
def leave_one_out(items: Sequence, fit: Callable, score: Callable,
                  key: Callable | None = None) -> dict:
    """Leave-one-(item/group)-out blind validation.

    For each item i: `params = fit(all items except i)`, then `score(item_i, params)`.
    The held-out item never informs the params it's scored under — the blind protocol.
    `key` groups items (e.g. by session) so a whole session is held out at once; default
    holds out one item at a time.

    `fit(train_items) -> params` (any object), `score(item, params) -> float`.
    Returns per-item scores, their mean (the blind aggregate), and the groups."""
    items = list(items)
    if key is None:
        groups = {i: [it] for i, it in enumerate(items)}
        member_of = {id(it): i for i, it in enumerate(items)}
        group_of = lambda it: member_of[id(it)]
    else:
        groups = {}
        for it in items:
            groups.setdefault(key(it), []).append(it)
        group_of = key
    per = {}
    for g, members in groups.items():
        train = [it for it in items if group_of(it) != g]
        params = fit(train)
        per[g] = [score(it, params) for it in members]
    flat = [s for ss in per.values() for s in ss]
    return {"per_group": per, "scores": flat,
            "blind_mean": float(np.mean(flat)) if flat else float("nan"),
            "n_groups": len(groups)}


def blind_in_sample_delta(items: Sequence, fit: Callable, score: Callable,
                          key: Callable | None = None) -> dict:
    """The honesty gap: leave-one-out (blind) vs fit-on-everything (in-sample).

    A large positive delta (blind worse than in-sample) means the params are tuned to
    the corpus and won't transfer — exactly the overfit we're guarding against. Returns
    both means and `delta = blind_mean − in_sample_mean`."""
    loo = leave_one_out(items, fit, score, key)
    full = fit(list(items))
    in_sample = [score(it, full) for it in items]
    in_mean = float(np.mean(in_sample)) if in_sample else float("nan")
    return {"blind_mean": loo["blind_mean"], "in_sample_mean": in_mean,
            "delta": loo["blind_mean"] - in_mean, "loo": loo}
