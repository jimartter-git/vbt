# Watch IMU — the rep detector & velocity, end-to-end

> The watch-IMU modality's working manual: how a 200 Hz Apple Watch CSV becomes per-rep
> counts + velocity, what the **one lift-agnostic** segmenter does, where it's at target,
> and the honest misses. Counterpart to `docs/cv-fusion.md` (video) and a deepening of
> CLAUDE.md learnings #23–#28, #32 and the Track B section of `docs/classical-foundation.md`.

## The pipeline

```
raw CSV (CMDeviceMotion, ~200 Hz)         dataset/raw/<set_id>_watch.csv
  → ingest.load_session                   parse, time-base = device uptime seconds
  → velocity.vertical_acceleration        project userAccel onto gravity axis → a_vert (up+)
  → wave_segment.segment                  ONE config: displacement-wave rep segmentation
       ├ reps  = bottom→top up-excursions near the set's MODAL amplitude
       └ MV    = ZUPT velocity, mean over the ACTIVE concentric region
```

Two boards score it against Vitruve ground truth (per-rep `mean_velocity` rows):

| Board | What | Run |
|---|---|---|
| `scripts/wave_eval.py` | counts (ONE config) + per-lift bias; `--blind` = leave-one-session-out | `python analysis/scripts/wave_eval.py --blind` |
| `scripts/watch_vel_board.py` | per-rep velocity RMSE / r / bias vs target (r>0.95, SEE<0.07) | `python analysis/scripts/watch_vel_board.py` |

`scripts/coverage.py` reconciles the board's `SESSIONS` dicts against every
`dataset/raw/*_watch.csv` — run it at the start of any watch work and after any ingest
(CLAUDE.md #30); a watch CSV that isn't in both `SESSIONS` dicts is invisible to the board.

## Track B — one lift-agnostic, position-domain segmenter

The overfit we removed (CLAUDE.md #26 §1b): the PoC was velocity zero-crossings + **three
per-lift threshold regimes** (rows/bench/RDL). `wave_segment.py` replaces all of it with a
**single config** that reads the vertical-displacement WAVE and picks reps by STRUCTURE:

- **modal excursion** — a rep is a bottom→top up-excursion near the set's own median
  amplitude; a reposition wiggle is sub-modal (rejected by prominence + an amplitude floor,
  no threshold in metres or m/s);
- **alternating extrema** — bottoms and tops alternate; the walk keeps the more-extreme of
  any same-type pair so each top is consumed once;
- **cadence** — a minimum inter-rep spacing rejects a sub-rep hump double-counting;
- **terminal-anomaly strip** — the unrack/rerack/putdown family is removed *structurally*
  from the ENDS only (see below), never by a per-lift ROM/MV gate.

Drift control is principled: a gentle high-pass doubly-integrates accel→displacement only to
**locate** the turnarounds; the shipped per-rep velocity is then re-integrated with **ZUPT**
anchored AT those turnarounds (zero velocity at each top/bottom — the classical two-sided
constraint the rest of meVBT uses). MV = mean |v| over the **active concentric region**
(|v| ≥ 10 % peak, excluding the near-zero turnaround tails) — the SAME definition the CV
path uses, not a per-lift knob (CLAUDE.md #28).

### The terminal-anomaly strip — and why leading ≠ trailing

A setup/unrack and a putdown betray themselves at an END:

- **Trailing**: AMPLITUDE only. A trailing *time gap* is **ambiguous** and we refuse to key
  on it — a real paused rep (SQ-1: a full-ROM rep after an 8 s breath) and a rerack are
  indistinguishable by gap, amplitude, bottom position, AND eccentric depth. A trailing-gap
  rule dropped SQ-1's real rep to catch SQ-3's extra — a net wash that violates "never drop a
  full-ROM main-lift rep" (#15). So SQ-3's structurally-real-looking extra is an **honest
  limit**, not chased.
- **Leading**: sub-modal amplitude **OR isolated-by-gap** (learning #32). The leading end is
  *not* symmetric. A setup/unrack happens BEFORE the set — the lifter presses the bar off the
  hooks (a leading excursion), then SETTLES, so the first excursion is followed by an
  anomalously large gap before the rep rhythm begins. A real first rep is followed by a
  NORMAL inter-rep gap (any settling pause sits BEFORE rep 1, where there is no detected
  excursion to mis-strip). So **"first excursion followed by a gap ≫ the set's modal
  rhythm"** identifies the unrack unambiguously and cannot catch a real rep-1-after-a-breath.

The leading-gap threshold is a single global constant (`_LEADING_GAP_FRAC = 2.5`), parked in
a wide empirical gap — every real leading excursion sits ≤ 1.8× the modal gap; the two
06-18 incline-bench setups sit at 3.8× and 7.4×. Counts are 16/18 across the whole plateau
K ∈ [2.0, 3.5] (not knife-edge). Residual theoretical risk — a full rep 1 then a long
rest-pause before rep 2 — is behaviourally unusual; documented, not tuned away.

## Where it stands (18 watch sessions, ONE config)

**Counts: 16/18 EXACT · mean|Δ| 0.11 · blind (leave-one-session-out) delta +0.00** — no
per-session / per-lift tuning leak. Bench 5/5, incline bench 3/3, squat 3/4, rows 3/4,
RDL 2/2. The two misses are the documented honest limits:

- **ROW-3 −1** — an integration-merged turnaround (two reps share a shallow intervening
  minimum below prominence; under-count).
- **SQ-3 +1** — a fast touch-and-go extra excursion structurally identical to a real rep by
  amplitude, gap, bottom position AND eccentric depth (the trailing-gap ambiguity above).

**Velocity: overall calibrated RMSE 0.071 m/s (target SEE < 0.07)**, dominated by a CONSTANT
per-lift offset (wrist vs bar, #4) — the shippable accuracy *after* a one-number calibration:

| lift | reps | RMSE | RMSE (calibrated) | bias (wrist−bar) | note |
|---|---|---|---|---|---|
| ROW | 39 | 0.064 | 0.063 | +0.013 | ✓ at target |
| RDL | 16 | 0.092 | 0.044 | −0.080 | ✓ — bias = the wrist-vs-hip-hinge offset |
| BN  | 50 | 0.107 | 0.074 | +0.078 | slow/paused/supine → low single-integration SNR |
| SQ  | 40 | 0.091 | 0.080 | +0.043 | narrow MV band caps r |
| IB  | 30 | 0.132 | 0.076 | +0.108 | incline bench, newest data |

Fixing the IB counts (16/18) also tightened IB velocity (calibrated RMSE 0.093 → 0.076) with
the MV *definition* unchanged — correct rep boundaries, not a re-tuned number.

### Interpretable, not lucky — the velocity ceiling on slow lifts

Per-rep Pearson r is **statistically capped** on slow, narrow-MV lifts, and this is a
property of the lift, not a pipeline bug (CLAUDE.md #25): a bench rep spans only ~0.19–0.40
m/s, so a 10-point correlation is bounded well below 0.95 for ANY tool (SmartBarbell agg
r ≈ 0.94 and misses > 0.95 on the same slow benches). r > 0.95 is a **wide-range / fast-lift**
metric — rows and RDL approach it, bench/squat/incline cannot. The defensible standard there
is **match the bar's velocity-LOSS shape and report an interpretable bias + confidence**, not
chase a correlation the dynamic range forbids.

We measured the velocity *method* directly: the drift-removed bootstrap velocity correlates
better per-set (mean r 0.46 vs 0.17) but is noisier, and on the AGGREGATE it loses to the
shipped ZUPT-active MV on BOTH calibrated RMSE (0.085 vs 0.074) and velocity-loss error
(13.6 vs 12.0 pp). So the active-region ZUPT definition stays — it is the classical ceiling
here, not a local choice. The ~12 pp residual velocity-loss error on slow lifts is the
honest limit; the named unlocks are a gyro-fed Madgwick orientation (the schema now carries
`rotationRate`, #28) and the Achermann 100 Hz protocol.

## Files

| Path | What |
|---|---|
| `vbt_analysis/wave_segment.py` | the ONE-config position-domain segmenter (Track B) |
| `vbt_analysis/velocity.py` | gravity projection, `integrate_with_zupt`, active-region MV |
| `vbt_analysis/ingest.py` | CSV → DataFrame (legacy 11-col + gyro/mag columns, #28) |
| `scripts/wave_eval.py` | counts board (`--blind` = leave-one-session-out) |
| `scripts/watch_vel_board.py` | per-rep velocity board vs the r/SEE targets |
| `scripts/_watch_*.py` | per-session diagnostics (alignment, pos-cycle experiment) |
| `tests/test_wave_segment.py` | structural-core + round-trip unit tests (10) |
</content>
</invoke>
