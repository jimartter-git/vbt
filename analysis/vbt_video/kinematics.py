"""Scaling + kinematics — the shared back-end.

Pixels → meters → vertical velocity → per-rep metrics. Unlike the IMU path, video
gives **absolute position** (no integration drift), so velocity is a clean
derivative. We resample to a uniform time base first (phone video is VFR), then
segment concentric reps with the same logic family as the rest of meVBT.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np
from scipy.integrate import cumulative_trapezoid  # noqa: F401  (kept for parity/use)
from scipy.signal import butter, filtfilt, savgol_filter


# ---- Scaler seam: pixels -> meters ----
@dataclass
class PlateDiameterScaler:
    """Scale from a known plate diameter (default 0.45 m standard bumper)."""
    plate_m: float = 0.45

    def m_per_px(self, target_px: float) -> float:
        if target_px <= 0:
            raise ValueError("target_px must be > 0")
        return self.plate_m / target_px


# Body-segment lengths as a fraction of standing height (Drillis & Contini anthropometry).
# Used for the equipment-free pose path: the skeleton *is* the ruler once height is known.
_SEGMENT_HEIGHT_FRAC = {"forearm": 0.146, "upper_arm": 0.186, "hand": 0.108}


@dataclass
class AnthropometricScaler:
    """Scale from a body segment whose real length is known from the user's height —
    the pose path's px→m (no implement in frame). `target_px` is that segment's median
    pixel length (PoseTracker reports the wrist↔elbow forearm by default).

    Absolute scale is only as good as the height prior, BUT velocity *loss* (our headline
    signal) is relative and survives a scale error as long as it's consistent rep-to-rep.
    """
    height_m: float = 1.75
    segment: str = "forearm"

    def m_per_px(self, target_px: float) -> float:
        if target_px <= 0:
            raise ValueError("target_px must be > 0 (pose found no scale segment)")
        frac = _SEGMENT_HEIGHT_FRAC.get(self.segment)
        if frac is None:
            raise ValueError(f"unknown segment '{self.segment}'; have {list(_SEGMENT_HEIGHT_FRAC)}")
        return (self.height_m * frac) / target_px


def _candidate_concentrics(t, v, pos, fs):
    """All positive-velocity runs between velocity sign-changes (the tempo-invariant
    rep turnarounds), with a minimum duration to drop chatter. Returns a list of
    (start, end, peak_velocity, rom_m) — *ungated*; the caller decides what's a rep."""
    b, a = butter(2, min(0.99, 0.1 / (fs / 2)), btype="high")
    vh = filtfilt(b, a, v)
    sign = np.sign(vh); sign[sign == 0] = 1
    crossings = np.where(np.diff(sign) != 0)[0]
    bounds = [0, *crossings.tolist(), len(v) - 1]
    cands = []
    for s, e in zip(bounds[:-1], bounds[1:]):
        if e - s < max(2, int(0.12 * fs)):
            continue
        seg_v = v[s:e + 1]
        if seg_v.mean() <= 0:
            continue
        cands.append((s, e, float(seg_v.max()), float(pos[e] - pos[s])))
    return cands


def _merge_subrep_runs(cands, pos, sep_frac=0.2, overtop_frac=1.0):
    """Coalesce consecutive positive-velocity runs that belong to ONE rep.

    A real rep boundary requires the bar to RETURN toward the bottom between
    concentrics (bench→chest, squat→depth, deadlift→floor). A deadlift's
    knee/sticking-point velocity dip, though, creates a spurious sign-change
    MID-rep where the bar barely descends — splitting one pull into 2–3 runs (the
    ~2× over-count seen on the 06-13 deadlifts: a cleanly-tracked 8-rep set
    segmented into 17–21). Merge a run pair only when BOTH:
      (a) the intervening DESCENT is under `sep_frac` of a rep ROM — the bar didn't
          return to the bottom (a stall, not a real eccentric), AND
      (b) the next run doesn't rise more than `overtop_frac` of a rep ROM ABOVE the
          current rep's top — a sticking-point hump completes the SAME rep's range,
          whereas a rack-in / put-up phantom shoots well above lockout. Without (b)
          the merge would swallow a terminal rack-lift into the last real rep, whose
          now-inflated top makes the plausibility gate drop it → a lost real rep
          (caught by test_plausibility_gate_drops_rack_phantoms).
    Lifts that fully reset between reps are untouched: their inter-rep descents are
    ~full ROM, far above (a)'s threshold. Lift-agnostic — it keys on bar return, not
    on knowing it's a deadlift.

    `sep_frac=0.2` was set from the corpus: measured inter-run descents cleanly
    separate into mid-rep DIPS (≤0.04·ROM — the bar stalls without reversing) and
    real ECCENTRICS (≥0.32·ROM, even SQ-1's noisy low-res mirror clip and SQ-3's
    fast touch-and-go); 0.2 sits in that gap, biased toward the eccentric side so a
    real rep is never merged away (a main-lift regression is the line we don't
    cross — CLAUDE.md learning #15). 0.4 over-merged SQ-1's 0.32 eccentrics. Both
    thresholds are fractions of a PHANTOM-ROBUST rep ROM (median of the real
    eccentric descents, not the raw position range a single rack-lift would inflate).
    """
    if len(cands) < 2:
        return cands

    def _valley_drop(end_i, start_j):    # how far the bar fell from run-i's top into the gap
        hi = max(int(start_j), int(end_i))
        return float(pos[int(end_i)] - pos[int(end_i):hi + 1].min())

    span = float(np.percentile(pos, 95) - np.percentile(pos, 5))    # rough rep scale (for thresh)
    if span <= 0:
        return cands
    thresh = sep_frac * span
    # Phantom-robust rep ROM: the median of the *real* (≥thresh) inter-run descents —
    # those are true floor returns ≈ one rep ROM; a lone rack-lift can't move a median.
    descents = [_valley_drop(a[1], b[0]) for a, b in zip(cands, cands[1:])]
    real = [d for d in descents if d >= thresh]
    rep_rom = float(np.median(real)) if real else span
    overtop = overtop_frac * rep_rom
    merged = [list(cands[0])]
    for c in cands[1:]:
        prev = merged[-1]
        descent = _valley_drop(prev[1], c[0])
        overshoot = float(pos[int(c[1])] - pos[int(prev[1])])   # rise ABOVE the rep's current top
        if descent < thresh and overshoot <= overtop:           # stall within the rep → same rep
            prev[1] = c[1]
            prev[2] = max(prev[2], c[2])                # keep the stronger hump's peak
            prev[3] = float(pos[int(prev[1])] - pos[int(prev[0])])   # full up-travel
        else:
            merged.append(list(c))
    return [tuple(m) for m in merged]


def _segment_concentric(t, v, pos, peak_min, rom_min, fs, rep_gate="absolute",
                        rel_rom_frac=0.5, rel_peak_frac=0.25,
                        rom_floor=0.04, peak_floor=0.05):
    """Pick which candidate runs are real reps.

    - `rep_gate="absolute"` (default, validated): keep runs clearing fixed
      `rom_min` (real travel, the primary gate) and `peak_min` (a low noise gate
      kept BELOW grind speed so terminal reps survive). Byte-for-byte the v1 rule.
    - `rep_gate="relative"`: tempo-invariant gating. The discriminator is **peak
      velocity relative to the set median**, NOT ROM — because a fast touch-and-go
      or partial-lockout rep has a *small ROM but a normal peak* (you still moved
      the load), whereas jitter has a *low peak*. A fixed ROM gate silently drops
      those partial reps; peak-relative gating keeps them and still rejects jitter
      (which sits an order of magnitude below the set's median peak). A small
      absolute ROM floor removes high-jerk zero-travel spikes. `rel_rom_frac` is
      unused here (kept for signature stability). See docs/sources-and-fusion.md
      "Tempo-invariance".
    """
    cands = _candidate_concentrics(t, v, pos, fs)
    cands = _merge_subrep_runs(cands, pos)   # fuse deadlift double-bump sub-reps (see helper)
    if rep_gate == "absolute":
        return [(s, e) for (s, e, peak, rom) in cands
                if peak >= peak_min and rom >= rom_min]
    if rep_gate != "relative":
        raise ValueError(f"unknown rep_gate '{rep_gate}'; use 'absolute' or 'relative'")
    # Drop pure jitter (high-jerk zero-travel spikes) with a small absolute floor,
    # then gate on PEAK velocity relative to the set median (scale-invariant ratio).
    floored = [(s, e, peak, rom) for (s, e, peak, rom) in cands
               if peak >= peak_floor and rom >= rom_floor]
    if not floored:
        return []
    med_peak = float(np.median([c[2] for c in floored]))
    peak_gate = max(peak_floor, rel_peak_frac * med_peak)
    return [(s, e) for (s, e, peak, rom) in floored if peak >= peak_gate]


# --- Rep-plausibility (position-anchor) gate constants ---
# A real rep's concentric STARTS at the set's own bottom anchor (the more-consistent
# extreme — docs/sources-and-fusion.md "Tempo-invariance") and ends no higher than the
# set's top band; rack-in / put-down / near-failure lockout-drift phantoms violate one
# of those. The gate is TRAILING-ONLY: it strips anomalous reps from the set's END,
# stopping at the first in-band rep — the validated phantom family is terminal by
# mechanism (the lifter racks/sets down AFTER the last rep; learning #14), and judging
# mid/leading reps positionally mis-fires on distorted-geometry clips (dead-front
# ROW-4: real reps at +0.8–1.6×ROM). Corpus evidence (2026-06-11): trailing phantoms
# deviate 0.68–3.3×ROM (neighbor-tolerant) while every real trailing rep is ≤0.33×ROM —
# a wide separation, so the thresholds are not finely tuned. All thresholds are
# fractions of the set's own median ROM (scale- and tempo-invariant).
_ANCHOR_DEV_FRAC = 0.5      # start-deviation (vs median, neighbor-tolerant) → anomalous
_OVERTRAVEL_FRAC = 1.0      # end ABOVE median end by this × median ROM → anomalous
#   (one-sided: ending BELOW the band is a partial/grindy rep — kept and flagged, never cut)
_MIN_REPS_FOR_GATE = 4      # need a meaningful median before trusting set statistics
_GATE_MAX_START_MAD = 0.25  # applicability: if MAD(start)/median ROM exceeds this, the
#   trajectory's positions are too incoherent for position plausibility — gate abstains
#   (trustworthy flow tracks measure ≤0.13; dark-iron resonators 0.5–2.6: huge margin)


def _plausibility_gate(reps):
    """Strip TRAILING candidate reps that don't anchor at the set's own bottom/top
    bands — the rack-in / put-down / near-failure lockout-drift phantoms (the
    over-count that also corrupts velocity-loss; learning #14).

    Start deviation is neighbor-tolerant (min of |start − median| and the step from
    the previous rep), so a slowly drifting bottom (posture creep, row arc) never
    reads as anomalous while an isolated terminal jump does. The gate ABSTAINS
    entirely when the track's start positions are incoherent (MAD > 0.25×ROM) —
    position plausibility means nothing on positions you can't trust (the same
    honest-abstention rule as detect-path velocity)."""
    if len(reps) < _MIN_REPS_FOR_GATE:
        return reps
    starts = np.array([r["pos_start"] for r in reps], dtype=float)
    med_start = float(np.median(starts))
    med_end = float(np.median([r["pos_end"] for r in reps]))
    med_rom = float(np.median([r["rom"] for r in reps])) / 100.0   # cm → m
    if med_rom <= 0:
        return reps
    if float(np.median(np.abs(starts - med_start))) > _GATE_MAX_START_MAD * med_rom:
        return reps                       # positions incoherent → abstain

    def _anomalous(i):
        sdev = abs(starts[i] - med_start)
        if i > 0:                         # neighbor tolerance (drift-proof)
            sdev = min(sdev, abs(starts[i] - starts[i - 1]))
        over = reps[i]["pos_end"] - med_end
        return (sdev > _ANCHOR_DEV_FRAC * med_rom
                or over > _OVERTRAVEL_FRAC * med_rom)

    n = len(reps)
    while n > 3 and _anomalous(n - 1):    # strip from the END; stop at an in-band rep
        n -= 1
    kept = reps[:n]
    if len(kept) != len(reps):
        for i, r in enumerate(kept, 1):
            r["rep_index"] = i
    return kept


def apply_plausibility(reps):
    """Post-hoc plausibility gate for reps already produced by `trajectory_to_reps`.

    The AUTO path applies the gate AFTER candidate selection (on the winning track
    only) — gating every candidate's count BEFORE selection changes the
    confidence×regularity scores and can flip the pick onto a decoy (verified on
    20260609-BN-4: pre-selection gating flipped the winner, 12→3). Post-selection,
    the validated selection behaviour is untouched and the gate is purely an output
    filter. `partial_rom` flags are recomputed on the kept reps (the phantom runs
    no longer contaminate the median)."""
    kept = _plausibility_gate([dict(r) for r in reps])
    if len(kept) != len(reps) and kept:
        med = float(np.median([r["rom"] for r in kept]))
        for r in kept:
            if med > 0 and r["rom"] < 0.7 * med:
                r["flag"] = "partial_rom"
            elif r.get("flag") == "partial_rom":
                del r["flag"]
    return kept


def trajectory_to_reps(track_traj, m_per_px, peak_min=0.12, rom_min=0.25,
                       rep_gate="absolute", rom_floor_frac=0.0, plausibility=False):
    """`track_traj` = N x 3 (t, cx, cy) px. Returns list of per-rep dicts.
    `rep_gate`: "absolute" (fixed ROM/peak, validated) or "relative" (adaptive,
    tempo-invariant — see `_segment_concentric`). `plausibility`: apply the
    position-anchor rep-plausibility gate (see `_plausibility_gate`; default off —
    the validated paths are unchanged; the auto path enables it)."""
    t = track_traj[:, 0].astype(float)
    y_px = track_traj[:, 2].astype(float)
    # image y grows DOWNWARD → bar up = y decreasing → vertical position (up +):
    pos = (-y_px) * m_per_px

    # de-duplicate / enforce increasing time, then resample to uniform dt (VFR-safe)
    keep = np.concatenate([[True], np.diff(t) > 1e-6])
    t, pos = t[keep], pos[keep]
    if len(t) < 8:
        return []
    dt = float(np.median(np.diff(t)))
    fs = 1.0 / dt
    tu = np.arange(t[0], t[-1], dt)
    posu = np.interp(tu, t, pos)

    win = max(5, int(round(0.10 * fs)) | 1)      # odd window ~100 ms
    win = min(win, (len(posu) // 2) * 2 - 1) if len(posu) > 7 else 5
    if win >= 5 and win < len(posu):
        posu_s = savgol_filter(posu, win, 2)
        vel = savgol_filter(posu, win, 2, deriv=1, delta=dt)
    else:
        posu_s = posu
        vel = np.gradient(posu, dt)

    segs = _segment_concentric(tu, vel, posu_s, peak_min, rom_min, fs, rep_gate)
    out = []
    for i, (s, e) in enumerate(segs, 1):
        seg_v = vel[s:e + 1]
        peak = float(seg_v.max())
        active = np.where(seg_v >= max(0.05, 0.1 * peak))[0]
        a0, a1 = int(active[0]), int(active[-1])
        out.append({
            "rep_index": i,
            "t": round(float(tu[s]), 3),                            # rep start time (s)
            "t_end": round(float(tu[e]), 3),                        # rep end time (s)
            "mean_velocity": round(float(seg_v[a0:a1 + 1].mean()), 3),
            "peak_velocity": round(peak, 3),
            "rom": round(float(posu_s[e] - posu_s[s]) * 100, 1),   # cm
            # concentric start/end position (m, up-positive, arbitrary origin) — the rep
            # boundaries the manual editor binds to, and the plausibility gate's anchors
            "pos_start": round(float(posu_s[s]), 3),
            "pos_end": round(float(posu_s[e]), 3),
        })
    # Rep plausibility BEFORE the partial/floor logic, so phantom runs (rack-in,
    # un-rack, lockout drift) don't contaminate the medians those rules use.
    if plausibility:
        out = _plausibility_gate(out)
    # Count vs measure: flag reps whose ROM is well under the set median as
    # `partial_rom` so downstream velocity/loss comparisons can exclude them
    # (a partial/no-lockout rep is counted, but isn't apples-to-apples). See
    # docs/sources-and-fusion.md "Tempo-invariance".
    if out:
        med = float(np.median([r["rom"] for r in out]))
        for r in out:
            if med > 0 and r["rom"] < 0.7 * med:
                r["flag"] = "partial_rom"
        # Optional relative-ROM floor: REJECT (don't just flag) reps whose ROM is well below
        # the set median — high-frequency detection jitter (DetectTracker) makes tiny-ROM
        # spurious reps; a real fatigued rep keeps most of its ROM. Scale-invariant. Default
        # 0 = off (flow path unchanged); DetectTracker uses ~0.5.
        if rom_floor_frac > 0 and med > 0:
            out = [r for r in out if r["rom"] >= rom_floor_frac * med]
            for i, r in enumerate(out, 1):
                r["rep_index"] = i
    return out
