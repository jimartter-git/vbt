"""Track-honesty checks — does a CV count come from a track that rides the BAR?

The generalization trap (CLAUDE.md learning #26, docs/classical-foundation.md §1a):
a rep COUNT can be right for the wrong reason. Flow faithfully tracks whatever it is
seeded on, so a decoy that happens to oscillate at rep cadence (a rack-stored plate
the bar sweeps past, a mirror reflection, the lifter's hip — the #17 *body-lock trap*)
can produce a plausible count from a meaningless track. Nothing in the pipeline today
verifies the track is on the working plate; only a human watching the overlay caught
the body-lock.

These checks reconstruct, WITHOUT ground truth, the signatures a real working-plate
track has and a decoy lacks:

  * **vertical-dominance** — a barbell lift moves the plate mostly UP/DOWN; over a set
    the vertical span dwarfs the horizontal one (|Δy| ≫ |Δx|). The un/rerack transit
    (learning #25) is the horizontal exception, but it's a small fraction of a set.
  * **periodicity** — the plate trajectory is quasi-periodic (rep after rep); a decoy
    parked in clutter, or a one-way drift, is not.
  * **motion presence** — the plate travels well over a fraction of its own diameter;
    a static rack plate barely moves (this mirrors the existing `static_track_suspect`
    guard, 0.30×target_px).
  * **seed-jitter stability** — perturb the seed a few px / a few frames and a true
    plate track returns the SAME count; a decoy's count is brittle. (Needs re-runs, so
    it takes a `count_fn` callable supplied by the harness — testable with a stub.)

Thresholds here are GLOBAL and physically motivated (one parameter set across all
lifts — the anti-overfitting principle), reusing the codebase's existing static-seed
constant. They are deliberately lenient: the goal is to REJECT obvious decoys, not to
hairline-tune a number. A flagged track is "don't trust this count," not "wrong."
"""
from __future__ import annotations

import numpy as np

# Mirror pipeline.VideoVelocitySource's static-seed guard: a track whose vertical span
# is under 0.30× the plate diameter is almost certainly a static rack/background plate.
_STATIC_MOTION_FRAC = 0.30
# A vertical lift's plate trajectory spans more vertically than horizontally. Lenient
# (≥1.2×) so a diagonal/perspective view or a side-on row (which still rises > it drifts)
# passes, while a horizontally-oscillating decoy or a body-lock hip track fails.
_MIN_VERTICAL_DOMINANCE = 1.2
# Quasi-periodic rep trains autocorrelate strongly at the rep lag. 0.3 separates a real
# rep cadence (typically 0.5–0.9) from aperiodic drift/clutter, well below either.
_MIN_PERIODICITY = 0.30


def robust_span(x) -> float:
    """5–95 percentile range — a robust peak-to-peak immune to a single bad frame."""
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return 0.0
    return float(np.percentile(x, 95) - np.percentile(x, 5))


def vertical_dominance(traj) -> float:
    """|Δy span| / |Δx span| of the track (N×3 t,cx,cy). >1 = moves more vertically
    than horizontally — the signature of a barbell lift seen on the plate."""
    traj = np.asarray(traj, dtype=float)
    if traj.ndim != 2 or traj.shape[0] < 3:
        return 0.0
    xspan = robust_span(traj[:, 1])
    yspan = robust_span(traj[:, 2])
    return yspan / (xspan + 1e-9)


def motion_presence(traj, target_px) -> float:
    """Vertical span as a multiple of the plate diameter (px). A real lift travels
    well over a plate; a static rack plate barely moves. NaN if target unknown."""
    if not target_px or target_px <= 0:
        return float("nan")
    traj = np.asarray(traj, dtype=float)
    if traj.ndim != 2 or traj.shape[0] < 3:
        return 0.0
    return robust_span(traj[:, 2]) / float(target_px)


def periodicity(y, min_lag=3) -> tuple[float, int]:
    """(strength 0..1, dominant lag) of a 1-D signal via normalized autocorrelation.

    Detrends, autocorrelates, and returns the strongest autocorrelation peak at a lag
    ≥ `min_lag` and ≤ N/2 (the rep period). A quasi-periodic rep train peaks sharply;
    drift/noise does not. Lag is in samples (frames), not seconds."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 2 * min_lag + 2:
        return 0.0, 0
    # remove the full linear trend (slope AND intercept) so a one-way drift (putdown)
    # detrends to ~0 and can't fake periodicity
    t = np.arange(n)
    y = y - np.polyval(np.polyfit(t, y, 1), t)
    denom = float(np.dot(y, y))
    if denom <= 1e-12:
        return 0.0, 0
    ac = np.correlate(y, y, mode="full")[n - 1:] / denom
    hi = max(min_lag + 1, n // 2 + 1)
    window = ac[min_lag:hi]
    if len(window) == 0:
        return 0.0, 0
    k = int(np.argmax(window))
    return float(max(0.0, window[k])), int(min_lag + k)


def seed_jitter_stability(count_fn, perturbations, base_count=None) -> dict:
    """Re-run a count under small seed perturbations and measure agreement.

    `count_fn(dx, dy, dt) -> int|None` re-runs the estimator with the seed nudged by
    (dx, dy) px and (dt) s; the harness supplies it (so this is unit-testable with a
    stub and doesn't import the heavy pipeline). `perturbations` is a list of
    (dx, dy, dt). A true plate track returns the same count under jitter; a decoy is
    brittle. Returns the fraction matching the base count + the raw counts."""
    counts = []
    for dx, dy, dt in perturbations:
        try:
            counts.append(count_fn(dx, dy, dt))
        except Exception:
            counts.append(None)
    if base_count is None:
        valid = [c for c in counts if c is not None]
        base_count = int(np.bincount(valid).argmax()) if valid else None
    n = len(counts) or 1
    agree = sum(1 for c in counts if c is not None and c == base_count) / n
    return {"base_count": base_count, "counts": counts, "agreement": round(agree, 3),
            "stable": agree >= 0.6}


def track_honesty(traj, target_px=None, reps=None,
                  min_vertical_dominance=_MIN_VERTICAL_DOMINANCE,
                  min_periodicity=_MIN_PERIODICITY,
                  min_motion=_STATIC_MOTION_FRAC) -> dict:
    """No-ground-truth verdict on whether a track plausibly rides the working plate.

    Returns the three frame-only metrics, a `flags` list of failed checks, and an
    overall `honest` bool. `reps` (optional) is only used to report the count alongside.
    seed-jitter is reported separately by the harness (it needs estimator re-runs)."""
    traj = np.asarray(traj, dtype=float)
    vdom = vertical_dominance(traj)
    per, lag = periodicity(traj[:, 2]) if traj.ndim == 2 and traj.shape[0] >= 3 else (0.0, 0)
    motion = motion_presence(traj, target_px)
    flags = []
    if vdom < min_vertical_dominance:
        flags.append("not_vertical_dominant")
    if per < min_periodicity:
        flags.append("aperiodic")
    if motion == motion and motion < min_motion:   # NaN (unknown target) → skip
        flags.append("static_track")
    return {
        "vertical_dominance": round(vdom, 3),
        "periodicity": round(per, 3),
        "period_lag": lag,
        "motion": (round(motion, 3) if motion == motion else None),
        "n_reps": (len(reps) if reps is not None else None),
        "flags": flags,
        "honest": len(flags) == 0,
    }
