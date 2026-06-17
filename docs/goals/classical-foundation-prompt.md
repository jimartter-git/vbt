# Goal prompt — classical foundation & anti-overfitting guardrail

Paste the block below into a fresh session to drive this work. It is **repeatable**: each run
syncs, reads the plan, finds the current track from git history, advances it, and stops at a
validated checkpoint. Full design rationale: [`docs/classical-foundation.md`](../classical-foundation.md)
(and CLAUDE.md learning #26).

---

```
GOAL: Build the classical (non-ML) foundation for VBT's CV and watch-IMU estimators on a
generalization guardrail, so the numbers survive a consumer app instead of overfitting our
tiny corpus. Full plan: docs/classical-foundation.md (and CLAUDE.md learning #26). Read both
before doing anything.

START EVERY RUN BY:
1. Syncing per CLAUDE.md's branch protocol (fetch --prune, fast-forward the canonical branch).
2. Reading docs/classical-foundation.md, then `git log --oneline -15` to see which track
   (A→B→C) is in progress and what's done. Pick up the earliest unfinished track.

THE BAR (don't declare done until met, measured BLIND on held-out data):
- CV: perfect on reps (main lifts first, learning #15), competitive on velocity vs SmartBarbell
  where scale is recoverable; every reported count backed by a track that passes honesty checks.
- Watch IMU: perfect on reps across all lifts with ONE parameter set; velocity interpretable
  (bias + confidence + a stated reason when offset, e.g. the RDL hinge anchor).
- Fused: near-perfect, the two sources cross-checking.

NON-NEGOTIABLE PRINCIPLES (from the doc — enforce them, don't relitigate):
- Separate PRODUCT-LEGITIMATE inputs (user tap / plate-confirm) from ORACLE inputs (seeds/rim
  registered in cv_eval.py::CLIPS because a prior session already found the answer). Headline
  ONLY the seed-free / blind number; report oracle/simulated-tap runs separately and labeled.
- ONE parameter set across lifts and clips, or it doesn't count. No per-lift threshold regimes.
- Right count ≠ right track. Prove track/segmentation honesty WITHOUT ground truth
  (seed-jitter stability, vertical-dominance, periodicity, working-plate priors).
- Validate BLIND: freeze params, score on clips/sessions that didn't inform them (leave-one-out).
- Interpretable > occasionally-accurate. Every velocity ships with bias + confidence.
- Do NOT headline a new number until it survives the blind guardrail. If a change only wins
  in-sample, say so and don't ship it as progress.

THE WORK, IN ORDER (A→B→C; finish and validate each before the next):

TRACK A — the generalization guardrail (the instrument; build first):
- Add input-provenance tagging to the eval harness: every run labeled seed-free / simulated-tap
  / oracle; compute the headline score from seed-free only.
- Add a leave-one-clip-out / leave-one-session-out protocol (frozen params, blind scoring).
- Add no-ground-truth track-honesty checks: seed-jitter stability, |Δy|≫|Δx| for vertical lifts,
  trajectory periodicity, working-plate priors (near hands/floor; two plates move together).
- Acceptance: harness scores a brand-new clip/session with ZERO per-clip config and emits
  (count, velocity, track-honesty pass/flag, blind-vs-in-sample delta). Unit-tested.

TRACK B — watch: one lift-agnostic, position-domain rep segmenter (kills the per-lift thresholds):
- Double-integrate accel→velocity→vertical DISPLACEMENT with principled drift control (ZUPT
  anchors, not a magic high-pass cutoff). Read the displacement WAVE.
- Reps = the quasi-periodic excursions between the set's own two recurring levels, picked by
  structure (alternating extrema, prominence vs the set's MODAL excursion, cadence spacing).
  Reject unrack (one-time non-repeating), reposition (sub-modal wiggle), putdown (terminal
  one-way) structurally — not by ROM/MV thresholds. Generalize learning #25's position-cycle
  detector (it already hit r 0.82–0.95 on bench) across row/bench/squat/RDL.
- Acceptance: exact counts across the corpus with ONE config, no per-lift thresholds; per-lift
  velocity bias/confidence surfaced; held-out sessions hold up. Validate under Track A.

TRACK C — CV: harden seed-free localization + make track-honesty a GATE:
- Strengthen the auto path's plate localization with the working-plate priors so candidate
  generation proposes the bar plate over rack/mirror decoys.
- Make track-honesty a rejection gate, so a passing count IMPLIES a correct track.
- Demote registered CLIPS seeds to "simulated user tap" in scoring (Track A provenance).
- Acceptance: seed-free counts at/over today's tap-path counts on the main lifts, blind; every
  count backed by an honest track; competitive velocity where scale is recoverable.
  (CV videos are 130–160MB in R2 via vbt_video/clip_store.py::resolve_clip — network permitting.)

WORKING RULES:
- Commit + push to the canonical branch at every validated checkpoint (ephemeral container).
- Keep all 50+ existing tests green; add tests for every new guardrail/segmenter behavior.
- Update docs/classical-foundation.md status + add a CLAUDE.md learning when a track lands.
- If a step needs a decision I can't infer (scope, a real trade-off), ask before guessing.
- No Xcode in this container (can't compile Swift); mirror any Swift-side metric change but
  flag it for first-build. ML (learned plate/IMU detectors) stays deferred — judged against
  this guardrail when its time comes.

END STATE: all three tracks landed and passing the blind guardrail; the bar above met; the
plan doc and CLAUDE.md reflect reality.
```
