# Classical foundation & the anti-overfitting guardrail

> **To drive this work:** paste the repeatable goal prompt in
> [`docs/goals/classical-foundation-prompt.md`](goals/classical-foundation-prompt.md) into a
> fresh session — it syncs, reads this doc, finds the current track, and advances it.

## Status (source of truth — each session ticks this)

- [ ] **Track A — generalization guardrail** (not started): provenance split, leave-one-out,
  no-GT track-honesty checks.
- [ ] **Track B — watch position-domain wave segmenter** (not started): one lift-agnostic
  detector replacing the per-lift threshold stack.
- [ ] **Track C — CV seed-free localization + track-honesty gate** (not started).

Update this list (and add a CLAUDE.md learning) when a track lands. Detail below.

---

**Status: design note / active plan (2026-06-17).** This is the foundation we build the
deterministic (non-ML) CV and watch-IMU estimators on *before* introducing learners. It
exists because of a specific, well-founded worry, stated by the project owner:

> I'm not confident we've maximized our classical algorithms. I suspect the CV seeds are
> often wrong even when the rep count is right. I don't think we're logically reading the
> watch's vertical waves and picking what are clearly the reps vs unracking/repositioning.
> Some numbers are good, but I'm not confident they generalize — I worry individual sessions
> have gamed/overfit individual sets in a way that wouldn't survive a consumer app. Before
> ML, exhaust the classical approaches and build on the most solid foundation we can.

**The goals this foundation serves** (unchanged, restated as the bar):
- **CV: perfect on reps, competitive on velocity.**
- **Watch IMU: perfect on reps, interpretable on velocity.**
- **Fused: near-perfect.**

"Interpretable" is deliberate: a watch velocity we can *explain and trust* (with its bias and
confidence) beats a raw number that's occasionally accurate by luck. The RDL case is the
example — the wrist under-reads the bar by ~0.21 m/s because it hangs at arm's length off a
hip hinge; the *shape* (velocity-loss) is right. Interpretable = we surface "this is the wrist,
not the bar; here's the offset and confidence," not a silent wrong number.

---

## 1. The diagnosis — where overfitting actually hides (with evidence)

This is not a hypothetical. Three concrete surfaces, found in the code 2026-06-17:

### 1a. CV: the headline numbers ride a per-clip oracle
`analysis/scripts/cv_eval.py::CLIPS` is a per-clip parameter table carrying **hand-registered
seeds** — literal pixel coordinates of where the working plate is, e.g.
`"20260616-BN-1": {"flow": (156, 732, 60, 60, 0.3)}` — plus per-clip `angle`/`plate`/`kind`/
`rim_px`. The "reps 0.12, human-grade, beats SmartBarbell" headline is the `--gate`/`--tap`
path, which **consumes those registered seeds**. That is a known-good answer baked into the
benchmark. A consumer app has none of it at first contact.

- The **product-legitimate** inputs (a user *tap* in-app, a user *plate-confirm* of the rim —
  learnings #10, #18) genuinely exist as a UI surface and are fair game.
- The **oracle** inputs (a seed/rim registered in CLIPS *because a prior session already found
  the right answer*) are not — using them to score generalization is circular.
- Today the two are conflated. The defensible generalization number is the **seed-free `auto`
  path** (`VideoConfig(tracker="auto")`, `seed=None`), and even it only verifies
  "confidence × cadence-regularity" + a static-seed guard. **Nothing checks the track is on the
  bar vs a decoy oscillating at rep cadence** — the "right reps, wrong reason" risk. Learning
  #17's *body-lock trap* already proves it: a seed on the lifter's hip passes every automated
  check; only a human watching the overlay caught it.

### 1b. Watch: velocity zero-crossings + three per-lift threshold regimes
`vbt_analysis/rep_detect.py::detect_turnarounds` integrates accel → a drifty velocity →
high-pass → zero-crossings → amplitude gate. The whole `decouple` mechanism in that file is a
single cutoff knob fighting itself (a high cutoff counts paused reps but phase-shifts the
anchors and inflates velocity). Then the cleanup is hardcoded **per lift**:
- rows/squat → `velocity.gate_reps` (ROM/MV ≥ 0.55× the set's robust median),
- bench → inline override `0.20 ≤ ROM ≤ 0.55 m, MV > 0.12`,
- RDL → inline override `0.40 ≤ ROM ≤ 0.70 m, MV > 0.10`.

**Three lifts, three regimes = the overfit.** We are not reading the vertical-position wave and
reasoning "these N excursions are reps; that one is the unrack; that sub-modal wiggle is a
reposition." We're thresholding magnitudes per lift.

### 1c. No blind validation anywhere
There is **no held-out / leave-one-out / blind protocol** in the repo. Every score is computed
on the same corpus the knobs were tuned on. `analysis/scripts/auto_detect_count.py` carries the
scar tissue: a comment admitting a past *"9/14 seeder that fell apart on fresh data."* The
overfit has bitten before and nothing currently catches it.

---

## 2. Principles (the rules we hold; extend, don't re-litigate)

1. **Separate product-legitimate inputs from oracle inputs.** A user tap / plate-confirm is a
   real app surface — allowed, but *labeled* as "simulated user input," never as the
   generalization score. A registered known-good seed/rim is an oracle — it may regression-guard
   a pipeline, but it must NOT count toward "does this generalize."
2. **One parameter set across lifts and clips, or it doesn't count.** Per-lift / per-clip knobs
   are the overfit. A change earns its place only if a single frozen configuration holds across
   the corpus *and* held-out data.
3. **Right count is not enough — the track/segmentation must be right for the right reason.**
   For CV: the trajectory must demonstrably ride the bar (track-honesty), not a cadence-matching
   decoy. For watch: the chosen excursions must be the actual reps, structurally distinguished
   from unrack/reposition/putdown — not whatever survives a magnitude threshold.
4. **Validate blind.** Tune on a subset, report on data the tuner never saw (leave-one-clip-out /
   leave-one-session-out). Headline the blind number.
5. **Interpretable > occasionally-accurate.** Every velocity ships with a bias estimate and a
   confidence, and a stated reason when it's offset (e.g. hinge anchor). A number we can explain
   is worth more than one that's sometimes right by luck.
6. **Exhaust classical before ML.** Learners (plate detector, IMU rep detector) come *after* the
   deterministic foundation is provably solid — they should be trained and judged against this
   same guardrail, not replace the need for it.

---

## 3. The three-track plan

### Track A — the generalization guardrail (the measuring instrument; build first)
Without it we cannot tell "the algorithm improved" from "we tuned the corpus." Deliverables:
- **Input provenance split** in the eval harness: tag every run as `seed-free` /
  `simulated-tap` / `oracle`, and compute the headline generalization score from the seed-free
  path only. Registered seeds become explicitly "simulated user tap," reported separately.
- **Leave-one-out / held-out protocol:** any threshold or parameter is frozen, then scored on
  clips/sessions that did not inform it. Report the blind number, not the in-sample one.
- **Track-honesty checks that need no ground truth** (catch "right count, wrong track"):
  - *seed-jitter stability* — perturb the seed by a few px / a few frames; a true plate track
    returns the same count, a decoy doesn't;
  - *vertical-dominance* — for vertical lifts the working-plate trajectory is |Δy| ≫ |Δx|
    (the un/rerack transit, #25, is the horizontal exception we already model);
  - *periodicity / cadence regularity* of the trajectory itself;
  - *working-plate priors* — near the hands (bench/squat) or the floor (deadlift), and (when
    visible) two plates translating together; a stored rack plate / mirror reflection fails these.
- **Acceptance:** the harness can score a brand-new clip/session with zero per-clip config and
  emit (count, velocity, a track-honesty pass/flag, and a blind-vs-in-sample delta).

### Track B — watch: one lift-agnostic, position-domain rep segmenter
Replace the velocity-zero-crossing + per-lift-threshold stack with a single wave analyzer:
- Double-integrate (accel → velocity → **vertical displacement**) with principled drift control
  (ZUPT anchors, not a magic high-pass cutoff).
- Read the **displacement wave**: reps are the quasi-periodic excursions between the set's own
  two recurring levels (top = standing/lockout, bottom = depth/chest/floor). Identify them by
  structure — alternating extrema with prominence relative to the set's *modal* excursion, and
  inter-rep spacing consistent with the set's cadence.
- Reject non-reps by their structural signature, not a per-lift threshold:
  - **unrack** = a one-time, non-repeating excursion to get into position (often different axis);
  - **reposition** = a sub-modal wiggle parked at a band;
  - **putdown** = a terminal one-way move that doesn't return.
- **One parameter set, all four lifts** (row/bench/squat/RDL), validated under Track A. The
  velocity that falls out is anchored at true turnarounds → clean concentric windows →
  interpretable, with the per-lift anchor bias (e.g. RDL wrist offset) measured and surfaced,
  not hidden.
- **Acceptance:** exact rep counts across the corpus with a single config and no per-lift
  thresholds; velocity bias/confidence reported per lift; held-out sessions hold up.
- Precedent to build on, not restart: learning #25's bench *position-cycle* detector already
  reached per-rep r 0.82–0.95 by exploiting the chest/lockout pauses — generalize that idea
  across lifts instead of three threshold regimes.

### Track C — CV: harden seed-free localization + bake in track-honesty
- Strengthen the `auto` path's **plate localization** classically using the working-plate priors
  above, so candidate generation proposes the bar plate (not a rack/mirror decoy) more often.
- Make **track-honesty a gate, not an afterthought**: a candidate that can't pass jitter-stability
  + vertical-dominance + periodicity is rejected even if its count looks plausible — so a passing
  count *implies* a correct track.
- Demote registered seeds to "simulated user tap" in scoring (Track A provenance split).
- **Acceptance:** seed-free counts at/over today's tap-path counts on the main lifts, with every
  reported count backed by a track that passes honesty checks; competitive velocity where the
  scale is recoverable (rim-confirm remains a legitimate product surface).

---

## 4. Sequencing & how we'll know we're done

**Order:** A → B → C. A is the instrument; B is the most clearly-overfit and fully local (no
video downloads); C needs R2 video and benefits from A's honesty checks.

**Done = the stated goals, measured blind:**
- CV exact on reps (main lifts first, learning #15) on held-out clips, no per-clip config, every
  count backed by an honest track; velocity competitive with SmartBarbell where scale is
  recoverable.
- Watch exact on reps across lifts with one config on held-out sessions; velocity interpretable
  (bias + confidence + reason surfaced per lift).
- Fused, near-perfect — the two sources cross-checking (velocity cross-correlation is already the
  time-sync, learning #23).

## 5. What we explicitly defer to ML — and why classical first
A learned plate detector/sizer and a learned IMU rep detector are the named long-term unlocks
(learnings #14, #20, #25). They are deferred, not dismissed, because: (a) a classical foundation
that we *understand* is debuggable and explainable in ways a black box isn't; (b) we need more
data first; and (c) **the learners must be judged against this same guardrail** — without Track A,
an ML model would overfit the tiny corpus exactly as a hand-tuned threshold does. Build the
instrument, exhaust the deterministic methods, *then* let learners earn their place on top.
