# CV fusion — the standalone video estimator

**Goal:** independent of the watch and multi-source fusion, the *video-only* path
should be a **best-in-class SmartBarbell competitor** — robust to different plate
types, video quality, camera angles, brief occlusion / out-of-frame, and gym
clutter (mirrors, bystanders, racks). Video is one input to the larger fusion
(`docs/sources-and-fusion.md`), but as a standalone part it should be as good as
it can be. This doc is the target, the current state, and the roadmap.

The measurable target is `analysis/scripts/cv_eval.py` — a scoreboard over every
clip with a ground-truth rep count. "Great" = beating the commercial app on count
and matching Vitruve, with honest confidence. The corpus grows as clips are added.

## Architecture (the seams — all swappable)

| Seam | Code | What |
|---|---|---|
| **Decode** | `frames.py` | PyAV, VFR-safe, re-iterable |
| **Tracker** | `track.py` | Flow (default), Plate (Hough+DP), CSRT, Pose — emit `(t,cx,cy)` + size + confidence |
| **Scaler** | `kinematics.py` | px→m: plate diameter *or* anthropometric (body segment) — chosen independently of the tracker |
| **Segmentation** | `kinematics.py` | turnaround-based concentric detection, absolute *or* relative gating |
| **Pipeline** | `pipeline.py` | ties it together, auto-fallback, scale confidence → `(reps, meta)` |
| **Fusion** | `scripts/fuse_cv.py` | combine flow + pose by cross-method consensus |

## What's implemented (and the scoreboard)

Default behaviour today, on the real corpus (vs Vitruve ground truth; SmartBarbell
in brackets):

Good / device-grade clips (must not regress):

| clip | scene | reps | ref | SmartBarbell | note |
|---|---|---|---|---|---|
| IB-1 | incline bench, iron 45+25, **side** | **10** | 10 | 10 | mean 0.44 m/s, **rmse 0.033 vs Stance** — velocity device-grade, scale *not* flagged |
| ROW-1/2/3 | barbell row, **bumper 45**, side/diagonal/front 720p | **10/10/10** | 10 | 10/9/10 | conf 1.00, occlusion never engages; front (ROW-3) → body-scale fallback under `--scale` |

Hard clips (the robustness wins):

| clip | scene | baseline | **now** | Vitruve | SmartBarbell |
|---|---|---|---|---|---|
| SQ-1 | squat, **bumper 45, side**, mirror/rack low-res | 8 | **10** | 10 | 5 |
| SQ-3 | squat, **bumper 45, side**, fast touch-and-go (adversarial) | 4 | **9** | 10 | 3 |
| SC-1 | DB press, **rubberized DB, diagonal** (pose-scaled) | pose 32 | **10** | 11 | — |
| DL-1 | deadlift, **bumper 45, diagonal** (front-quarter) | — | **2** | — | 2 (=) |

Capture conditions vary per clip by design (the lifter switches angle/speed/plate shot to
shot) — these are the **lifter-confirmed** per-clip conditions, mirrored in `cv_eval.py`
`CLIPS[*].scale` so `--scale` scales each clip on its own angle+plate.

(DL-1 count matches SmartBarbell exactly; its velocity reads ~1.5× high — a
*moderate* scale error that slips under the plausibility flag, the roadmap-#2 case.)

We **beat SmartBarbell on count everywhere there's a comparison** and ~match ground
truth on all clips — preserving the device-grade good cases (IB-1 byte-identical,
velocity included) while rescuing the ones that previously defeated every tracker
(SQ-3) or were written off as "CV unreliable here" (SC-1).

**Two findings from the corpus (design rules):**
- **Track the object, not the joint, when there's an object.** SC-1 pose (wrist
  landmark) invents reps side-on (32 / 45 vs GT 11); flow on the **dumbbell end**
  gets 10/11. Pose is the *fallback* for equipment-free / no-trackable-object cases,
  not the default when a plate/DB face is visible.
- **Relative gating assumes a healthy track.** Peak-relative gating recovers partial
  reps when the candidate runs are dominated by *real* reps. When the **tracker is
  broken** (pose garbage), candidates are dominated by noise, the median is noise, and
  relative gating admits *more* — it made SC-1-pose worse (32→45). No gating fixes a
  broken tracker; relative gating is for recovering partials on a track that held.

1. **Adaptive rep gating** (`rep_gate="relative"`). The rep discriminator is **peak
   velocity relative to the set median**, not absolute ROM — because a fast
   touch-and-go / partial-lockout rep has *small ROM but a normal peak*, while
   jitter has a *low peak*. Recovers partial reps a fixed ROM gate silently drops;
   still rejects chatter (scale-invariant ratio). Sub-median-ROM reps are flagged
   `partial_rom` for the count-vs-measure split. *(SQ-1: 8→10.)*

2. **Occlusion robustness** (`occlusion_robust`). On lost lock the tracker **coasts**
   through a short gap on the last velocity, and **re-acquires** by re-detecting the
   plate near the predicted position the instant it reappears — instead of freezing
   (which flattens the trajectory and erases reps). Re-acquire fires only after
   *sustained* loss and accepts only a near + right-sized detection (no snapping to a
   mirror reflection). *(SQ-3: lost-lock reps recovered.)*

3. **Auto-fallback** (`auto_occlusion`, default on). A low-confidence default flow
   track transparently retries occlusion-robust and keeps whichever held better.
   **No-op on healthy clips** (they never trip the threshold) — so the hard case is
   rescued without regressing the easy one. *(SQ-3: 4→9 automatically; SQ-1 stays 10.)*

4. **Scale confidence + honest-velocity flagging.** Two pose-free signals —
   plate-radius stability (`size_cv`) and bar-speed plausibility — produce
   `scale_confidence` + `scale_suspect`. A suspect scale marks reps
   `velocity_relative_only` rather than reporting a confident wrong m/s (the
   hex/low-res plate breaks the diameter ruler → count is trusted, velocity isn't).

The validated absolute/default path is byte-for-byte unchanged behind every flag.

## Generalized (automated) performance — honest status (2026-06-05)

⚠ **The scoreboard above uses MANUAL seeds (a human tapping the plate in frame 0).**
That is the with-a-human-in-the-loop number. The product won't always have that, so the
real question is the **fully-automated** result — run it with `cv_eval.py --auto`. On the
14-clip corpus today:

| regime | how it runs | count result | velocity |
|---|---|---|---|
| **Manual seed** (human tap) | hand-placed bbox on the bar plate | **~13/14 within ±1**, beats SmartBarbell wherever compared | device-grade only on clean side-on high-res (IB-1); diagonal/low-res ~2× |
| **Auto-seed flow — motion** (`auto_seed_motion`, the default) | picks the circle whose disc×column MOTION is highest, i.e. *the circle that moves*, no tap | **9/14 within ±1** (incl. IB-1, ROW-1, SQ-1/3, BN-2/3, DL-1/2/3); misses ROW-2/3, SC-1, BN-1, and the 2-rep DL-1-2024 | scale still per-clip (see #2) |
| *(old auto-seed — largest static blob)* | `auto_seed_bbox`, kept as fallback | **0/14** — grabbed a static wall/rack blob every time | n/a |
| **Seed-free pose** (wrist) | MediaPipe, no tap | good on **standing, big-ROM** lifts (deadlifts **10/10/11**, angled/front rows ±1); **over-counts** supine/side-on/isolation | **deadlift velocities within ~0.1 of Vitruve**; unreliable elsewhere |

**Verdict.** The zero-tap path is now **halfway sensible (9/14), not broken (0/14)** — the
motion auto-seeder finds the moving plate on most clips, and the planned tap-to-seed/adjust UX
covers the rest. The discriminator is **motion** (the bar plate sweeps its spot every rep;
rack-stored/background/mirror plates sit in dead pixels), combined disc×column so a static
plate stacked in a moving column still fails. Remaining gaps, each with a named roadmap item:

1. **Auto-seed is a heuristic, not yet a detector.** It still misses front/oblique rows, the
   supine BN-1, and isolation (SC-1) — and a good seed doesn't fix scale (velocities run high).
   The durable fix is **roadmap #6 (a learned plate/bar-end detector)**; `auto_seed_motion` is
   the bridge until then.
2. **Absolute velocity is not generally trusted yet** — only device-grade on clean side-on
   high-res. Diagonal plates read ~2× because the circular Hough measures the elliptical rim's
   minor axis (**roadmap #2: ellipse / user-confirmed diameter**). Velocity **loss** (relative,
   the headline fatigue signal) survives the scale error and IS robust.
3. **Pose is the seed-free safety net**, gated to where it's valid (standing, large wrist
   travel) — never supine/isolation. `fuse_cv.py`'s cross-method count check is the right
   mechanism, and `auto_seed_motion` now lets flow vote without a manual seed.

Net: **counts are production-ready behind a one-tap UX and ~9/14 fully hands-off; absolute
velocity is the remaining gap** (#2). Re-run the honest number any time with `cv_eval.py --auto`.

## Zero-tap rebuild — track-by-detection (2026-06-09)

The old zero-tap path (flow + a single auto-seed) was **8.5 mean rep-count error** on the
22-clip corpus (vs SmartBarbell **2.5**) and overfit — a 9/14 seeder that collapsed on fresh
data (rows 0/0/0/2, heavy bench 10/0/0/0). Rebuilt as **track-by-detection**
(`analysis/scripts/auto_detect_count.py`): per-frame multi-cue circle detection (grayscale +
**Canny-edge** Hough, the edge pass exposing dark-iron rims flow can't track) → anisotropic
track association → **oscillation-based** track selection → rep-band low-pass → tempo-invariant
relative gate + relative-ROM floor.

Track-by-detection alone reached **~2.5 = SmartBarbell parity** (beats SB on clutter/TnG,
loses on clean clips), because per-frame detection jitters and can pick a periodic decoy. The
fix was **fusion, not a single tracker**:

### ⚑ The no-tap AUTO path = flow ⊕ detect fusion (`tracker="auto"`) — BEATS SmartBarbell

`VideoVelocitySource(VideoConfig(tracker="auto"))`. **Candidate-generation + flow-VERIFICATION:**
the real blocker was plate *localisation* in clutter (mirror / hex / multiple plates) — a single
auto-seed picks a decoy, flow goes static, detect over-counts. So `seed_candidates()` proposes the
top-K moving circles (each sized to its rim **ellipse**, since a too-small hub seed makes flow
over-count), flow runs on each, and we **keep the candidate where flow holds lock** with a
plausible count (3–18) + regular cadence. If none holds (dark/low-texture iron) → DetectTracker
for the COUNT. Detect-style robustness for *finding*, flow's smoothness for *tracking*.

**Result (22-clip corpus, fully automatic, no tap, no gym config): mean rep-count error
8.5 → 1.36 → 0.55, vs SmartBarbell 2.57 — and 19/22 within ±1 vs SB's 13/21. Beats SB on both.**
Run it: `python analysis/scripts/cv_eval.py --auto`. It **generalises** (Equinox hex+mirror,
Westwood bumpers, a travel gym, side/front/behind angles, 30–60fps) and *improved the old corpus*
too (DL-1-2024 8→3, SC-1 9→11), fixed the Equinox squats (19/35→10/10), and beats SB on the RDLs
it failed (7 vs 1, 8 vs 4). The fix is method, not a gym/colour profile — single-method/profile
ideas (periodicity/motion-model/color/bilateral/twin-pair/PCA) all plateaued at ~2.5.

**Remaining errors (the honest few):** the dead-front row (ROW-4-0608, motion toward camera —
unrecoverable from video for anyone, SB also fails), a 2-rep clip where detect over-counts
(20240531-DL-1), and a couple dark-iron clips where flow goes static and detect over/under-counts
(BN-4-0609, ROW-2-0608). The durable lift for these is still a **learned plate detector**
(roadmap #6) feeding the same fusion back-end — but it is no longer needed to beat SB.

(Rejected en route, all plateaued at ~2.5 as single methods: periodicity-weighted selection,
motion-model association, color-blob cue, bilateral averaging, twin-pair selection, PCA
consensus. The win came from fusing the two complementary trackers, not from a better single one.)

### Velocity — also beats SmartBarbell (on the fatigue signal), honestly

Absolute velocity is **scale-limited at low res** (440px diagonal plates read ~2× — the
circular-Hough-vs-ellipse issue, roadmap #2; device-grade only on HD: IB-1 720p rmse 0.033).
But the product signal is velocity **LOSS**, which is **scale-invariant**. The fusion reports a
*reliable* velocity only when it picks **flow** (smooth trajectory); on a detect fallback (dark
plate) it **abstains** — count-only, reps flagged `velocity_relative_only`, `meta["velocity_
reliable"]=False` — rather than report a confident-wrong number (detect's jittery per-frame
centres ruin per-rep velocity). On the clips where we report (`vel_eval.py`):

**velocity-LOSS |err vs Vitruve| = 5.7 pp (OURS) vs 9.4 pp (SmartBarbell)** — we beat SB on the
fatigue signal too (e.g. DL-1 loss 6.9 vs SB 18.6 vs Vitruve 8.8; BN-1-0609 38.3 vs 34.8 vs
41.8), and abstain on the 3 dark-iron clips instead of guessing. Absolute m/s stays flagged
scale-suspect at 440px until roadmap #2 (ellipse / confirmed-diameter scale) or HD clips.

> ⚑ **Superseded by the full 2026-06-10 snapshot below** — the 06-09 dark-iron benches were
> added to the velocity board and (a) auto now picks **flow** on them (no longer abstains), and
> (b) two of them (BN-2/BN-4 0609) carry the near-failure over-count, which drags the all-clips
> loss number up. Apples-to-apples it's still a clear win; see the snapshot for the honest split.

## Full scoreboard snapshot (2026-06-10) — reps · velocity · velocity-loss · one-tap vs auto

The complete, current state of the three product metrics. Regenerate any time:
`cv_eval.py --auto` (reps, no tap), `cv_eval.py --adaptive` (reps, one-tap seeded), `vel_eval.py`
(velocity-loss). GT priority = Vitruve → Stance → logged `actual_reps` (the touch-and-go rows:
Vitruve under-counts, no Stance, SB partial → the lifter's logged count is GT).

### (1) Reps — GT vs SmartBarbell vs (A) auto/no-tap vs (B) one-tap/best-seed

| | SmartBarbell | (A) Auto, no tap | (B) One-tap, best seed |
|---|---|---|---|
| **Mean abs error** (unweighted) | **2.57** | **0.55** | **0.36** |
| **Mean abs error** (lift-weighted) | 2.54 | **0.48** | — |
| Exact (Δ=0) | 7 / 21 | 13 / 22 | 16 / 22 |
| Within ±1 | 13 / 21 | 19 / 22 | 20 / 22 |

**Lift-priority weighting** (learning #15): the backtest weights main lifts (squat/bench/deadlift
=1.0) over rows/RDLs (=0.5) over accessories (skull crushers/DB =0.25) — `cv_eval.py::lift_weight()`,
shown as a second summary line under `--auto`. It *widens* our lead (ours 0.55→0.48; SB 2.57→2.54):
our residual errors cluster in the down-weighted rows, SB's big misses are on the main lifts. **Judge
new CV changes on the lift-weighted number; never trade a main-lift regression for an accessory gain.**

- **Both our paths crush SB** (0.55 / 0.36 vs 2.57). SB's catastrophic misses are the deadlifts
  and dark-iron rows (DL-2 2/10, ROW-4 1/10, BN-1-0609 3/10); it's competitive only on clean clips.
- **One-tap buys ~0.2 rep over auto**, entirely by fixing auto's *over-counts* on clean clips
  (ROW-2/3 0601 11/12→10, DL-3 0605 11→10, DL-1-2024 3→2) — a seed pins the right plate so flow
  can't latch a second moving circle. That's the value of the UX tap.
- **It is NOT strictly better.** SC-1 is the honest counter-example: auto nailed 11, one-tap read
  10. Seeds can occasionally pick a slightly worse track.
- **Dark-iron (06-08/06-09): one-tap ≈ auto.** A real manual-seed search (flow on the top plate
  candidates) reproduced the auto count on **6 of 7** clips — auto's candidate-generation already
  finds the seed a human would tap. The tap adds nothing here.
- **ROW-4 (dead-front) — the one clip where a naive tap HURTS.** The working plates are edge-on
  (thin ellipses, untrackable as discs) and the obvious big black disc is a **rack-stored decoy**
  (verified: tapping it → 0 reps / `static_track_suspect`). Detect-by-detection (auto's 8) is
  genuinely the best available; there is no good disc to seed. This re-confirms learning #12.

### (2) Velocity + velocity-loss — auto, on the 13 Vitruve-velocity clips

| Set | reps GT→ours | Vit m/s | SB m/s | our m/s | Vit loss% | SB loss% | our loss% |
|---|---|---|---|---|---|---|---|
| SQ-1 0604 | 10→10 | 0.80 | 0.72 | 1.84 | 7.5 | 1.2 | 6.5 |
| SQ-3 0604 (fast TnG) | 10→10 | 0.79 | 0.80 | 1.72 | 30.1 | 2.4 | 26.1 |
| SC-1 0602 (DB press) | 11→11 | 0.38 | — | 0.93 | 26.7 | — | 65.2 ✗ |
| BN-1 0605 | 10→10 | 0.54 | 0.54 | 1.36 | 4.1 | 14.6 | 7.8 |
| BN-2 0605 | 10→10 | 0.65 | 0.63 | 1.26 | 20.7 | 17.3 | 16.8 |
| BN-3 0605 | 11→11 | 0.76 | 0.79 | 1.05 | 22.7 | 12.4 | 15.7 |
| DL-1 0605 | 10→10 | 0.96 | 0.70 | 2.43 | 8.8 | 18.6 | 3.5 |
| DL-2 0605 | 10→10 | 0.96 | 0.85 | 1.26 | 15.4 | — | 19.5 |
| DL-3 0605 | 10→11 | 0.82 | 0.68 | 2.73 | 5.7 | 4.3 | 7.6 |
| BN-1 0609 | 10→10 | 0.37 | 0.19 | 0.43 | 41.8 | 34.8 | 44.8 |
| BN-2 0609 | 10→11 | 0.41 | 0.38 | 0.71 | 26.5 | 24.4 | 43.0 ✗ |
| BN-3 0609 | 10→10 | 0.33 | 0.32 | **0.33** | 32.5 | 30.3 | 31.9 |
| BN-4 0609 (near-fail) | 10→12 | 0.30 | 0.29 | 0.41 | 44.6 | 26.5 | 23.4 ✗ |

**Velocity-loss |err vs Vitruve|:** apples-to-apples on the **11 common clips** (both report a
loss) = **OURS 6.2 pp vs SB 9.0 pp** — we win (all 11 are main lifts, so lift-weighting doesn't
change it). All-13 (incl. the two clips SB can't report) = 8.5 pp unweighted, **6.7 pp
lift-weighted** (the accessory SC-1, our worst loss miss, is down-weighted ×0.25 per learning #15).
SB's signature failure is **flattening the fatigue curve** (SQ-3: Vitruve 30%, SB 2.4%, us 26%) —
which is the whole VBT thesis. `vel_eval.py` prints both unweighted and lift-weighted.

**Absolute velocity (m/s): SB still wins** (SB mean abs err ≈ **0.07** vs Vitruve; ours dominated
by low-res scale inflation, e.g. DL-3 2.73 vs 0.82). BUT the scale error is **velocity/angle-
dependent, not uniform**: the slow heavy 06-09 benches scale *beautifully* (BN-3 exact 0.33=0.33,
BN-1 0.43 vs 0.37) while fast diagonal-bumper clips read ~2×. This is the roadmap-#2 case.

### (3) The two honest weak spots — same root cause, highest-leverage fix
- **SC-1 (DB press):** worst loss miss (65% vs 27%) — single-dumbbell tracking on a non-barbell
  lift, outside the core barbell wheelhouse.
- **Near-failure over-count = velocity-loss corruption.** The clips we over-count (BN-2/BN-4 0609
  → 11/12 vs 10) are the *same* clips whose loss is wrong (43%/23% vs 26%/45%): a phantom extra
  "rep" at the grindy end corrupts the "mean of last 2" in the loss formula. **The count error and
  the loss error are one bug — near-failure terminal-rep ambiguity** (exactly the "terminal reps
  are hardest" learning). **Fixing the near-failure over-count tightens BOTH counts and loss on the
  heaviest sets — the single highest-leverage CV improvement available right now** (doesn't need
  torch/HD; it's a segmentation problem: the lifter racks/drifts at lockout on a near-failure rep).

### Where this leaves the goal ("out-of-the-box better than SmartBarbell")
- **Reps: WON** (0.55 vs 2.57), fully automatic, generalizes across gyms/angles/plates/fps.
- **Velocity-loss (the fatigue signal / product thesis): WON** apples-to-apples (6.2 vs 9.0 pp).
- **Absolute velocity (m/s): OPEN** — SB wins; gated on either HD clips (user declined) or a
  learned plate-sizer for consistent rim measurement (**no torch in this container** → not
  buildable here today; classical Hough auto-sizing already proven unsafe to default-on, see
  roadmap #2). Velocity-loss being scale-invariant is why we win the signal that matters anyway.

> ⚑ **Superseded by the 2026-06-11 snapshot below** (the near-failure over-count fix +
> the ONE canonical loss). The tables above remain the honest 06-10 baseline.

## Full scoreboard snapshot (2026-06-11) — the near-failure fix + ONE canonical loss

Same corpus, same no-cheating rules as 06-10 (auto gets ONLY the clip path; GT/SB scoring-only).
Regenerate: `cv_eval.py --auto` · `vel_eval.py`. All 42 tests green; one-tap/manual paths
byte-identical (every change is auto-path-only or definition-level).

### What changed

1. **The near-failure over-count is FIXED — learning #14's "highest-leverage fix", landed.**
   A **rep-plausibility (position-anchor) gate**: real reps START at the set's own bottom
   band (the more-consistent extreme) and END no higher than its top band; rack-in /
   put-down / lockout-drift phantoms violate one of those by 0.68–3.3×ROM (neighbor-
   tolerant) while every real trailing rep on the corpus sits ≤0.33×ROM — wide separation,
   thresholds insensitive ±20%. `kinematics._plausibility_gate` + `apply_plausibility`;
   `VideoConfig.plausibility_gate` (default OFF). The auto path applies it to flow/profile
   picks. **Three design constraints, each validated by a failure** (do NOT re-litigate):
   - **Post-selection only.** Gating candidates BEFORE auto's flow-verification changes
     their counts/cadence-regularity scores and flips the pick onto a decoy (BN-4: 12→3).
   - **Trailing-strip only.** The phantom family is terminal by mechanism (the lifter
     racks/sets down AFTER the last rep). Judging leading/mid reps positionally kills real
     reps on distorted-geometry clips (dead-front ROW-4: 8→6 when gated globally).
   - **Abstain on incoherent positions** (MAD(start) > 0.25×median-ROM) **and on the
     detect fallback** — position plausibility needs position-trustworthy tracks
     (dark-iron ROW-1-0608, a count-right/position-garbage flow resonator: 10→0 without
     this; trustworthy flow tracks measure MAD ≤ 0.13, resonators 0.5–2.6).
2. **ONE canonical velocity-loss** — `analysis/vbt_analysis/metrics.py::velocity_loss_pct`:
   **best rep → mean of the last min(2, n−1) reps; <3 usable reps = NaN; phantom/missed
   excluded.** Previously FOUR divergent formulas (vel_eval best→mean-last-2, dataset
   `compare.py` best→last, `vbt_analysis.velocity` best→min, Swift `SetSummary` best→min) —
   loss numbers were silently incomparable across tools. Now vel_eval, compare.py,
   velocity.py and (mirrored, with tests) Swift `SetSummary` all share the definition.
   Measured on the board: the k=2 terminal window beats k=1 decisively (lift-weighted
   |err| 3.97 vs 5.57pp — single-terminal-rep noise is real); excluding `partial_rom`
   reps from the window is noise-level (<0.2pp) and asymmetric vs GT → off by default.
   **Re-baselining:** vel_eval already used this formula → board numbers comparable to
   06-10; `compare.py`'s printed VL changed semantics (was best→last) → its per-set VL
   columns re-baseline, labelled in its output.

### (1) Reps — auto/no-tap vs SmartBarbell (Δ from the 06-10 board in brackets)

| | SmartBarbell | Auto, no tap |
|---|---|---|
| **Mean abs error** (unweighted) | 2.57 | **0.32** [was 0.55] |
| **Mean abs error** (lift-weighted) | 2.54 | **0.25** [was 0.48] |
| Exact (Δ=0) | 7 / 21 | **16 / 22** [was 13] |
| Within ±1 | 13 / 21 | **21 / 22** [was 19] |

Movers (all improvements; **no clip got worse** — verified per-clip vs the 06-10 baseline):
BN-2-0609 11→**10**, BN-4-0609 12→**10** (the near-failure targets), ROW-2-0601 11→**10**,
ROW-3-0601 12→**11** (put-down phantoms — caught by END-overtravel: the bar travels
+2.5–3.1×ROM above the top band when stood up/racked). Every bench and squat on the corpus
is now EXACT. Remaining errors: ROW-3-0601 +1 · DL-1-2024 +1 (detect, 3 candidates < gate
minimum) · DL-3-0605 +1 (the 11th candidate starts at the floor and ends low — positionally
identical to a real grindy partial; one-tap fixes it, position plausibility honestly can't)
· ROW-2-0608 −1 · ROW-3-0608 +1 · ROW-4-0608 −2 (dead-front, defeats every tool; SB=1).

### (2) Velocity-loss — the count fix repairs the fatigue signal, as predicted

The two clips we over-counted were the two clips whose loss was corrupt — one bug, fixed
together: **BN-2-0609 loss err 16.5→3.3pp** (43.0→23.2 vs Vitruve 26.5), **BN-4-0609
21.2→1.4pp** (23.4→46.0 vs Vitruve 44.6).

| | 06-10 | **06-11** | SmartBarbell |
|---|---|---|---|
| apples-to-apples, 11 common clips | 6.2pp | **3.2pp** | 9.0pp |
| all 13 reported clips (unweighted) | 8.5pp | **6.0pp** | — |
| all 13 (lift-weighted) | 6.7pp | **4.0pp** | — |

Every MAIN-lift clip is now within 4.3pp of Vitruve. The one bad miss is unchanged:
SC-1 (DB press, accessory, ×0.25) 65.2 vs 26.7 — single-dumbbell tracking, outside the
barbell wheelhouse (roadmap: pose/watch fusion, not more plate CV).

### Where this leaves the goal
- **Reps: WON, harder** — 0.32/0.25 vs SB 2.57/2.54; 21/22 within ±1.
- **Velocity-loss: WON, ~3×** — 3.2pp vs 9.0pp apples-to-apples.
- **One-tap board: unchanged from 06-10** (0.36) — the gate is default-OFF outside the
  auto path, so the manual/one-tap paths are byte-identical (full suite re-verified).
  Note the auto path (0.32) now slightly BEATS the 06-10 one-tap number: the over-counts
  the tap used to buy back are gone.
- **Absolute velocity: still OPEN** (unchanged — gated on HD clips or a learned
  plate-sizer; neither buildable/approved here).

### Why the residual errors are at the segmentation floor (assessed, not assumed)
- **ROW-3-0601 +1**: a 4 cm mid-set micro-rep (0.12×median ROM). A flow-path relative-ROM
  floor CANNOT remove it without killing SC-1's real grindy rep 9 (also 0.12×median, GT
  rep) — measured, the two are numerically identical. Only peak-shape/prior/human-tap
  separates them. Don't re-try ROM floors here.
- **DL-3-0605 +1**: the 11th candidate starts at the floor and ends low — positionally a
  real grindy partial. The one-tap/manual editor is the resolution (per learning #11).
- **DL-1-2024 +1 / 0608 rows ±1–2**: detect-path/incoherent-position clips, below the
  plausibility gate's applicability by design (see learning #16).

## The LLM-tap experiment (2026-06-11) — simulating the one-tap UX end-to-end

An agent simulated the product's tap UX on the FULL corpus: viewed frames per clip,
placed a seed on the working plate, verified it (overlay across the clip + the
`static_track_suspect` guard as the "did my tap track?" feedback), re-tapped on obvious
failures — then ran `flow + relative gate + ellipse scale + plausibility gate` (= the
`--gate` board config; seeds registered in `CLIPS`). Also: the four 2026-06-10 Equinox
clips (2 squats, 2 RDLs; GT = lifter count, Vitruve crashed) were registered, extending
the corpus 22 → 26. On the 26-clip corpus:

| | Auto (no tap) | **LLM-tap** (re-tap loop ≤4 tries, + auto fallback where no valid tap exists) |
|---|---|---|
| reps mean abs err (unweighted) | 0.31 | **0.23** |
| reps mean abs err (lift-weighted) | 0.24 | **0.16** |
| exact / within ±1 | 19 / 24 of 26 | **21 / 25** of 26 |
| velocity-LOSS \|err vs Vitruve\| (13 GT clips) | **6.0pp** | 7.7pp |

⚠ Corrected 2026-06-11 (lifter-audited): the experiment's first scoring (0.27/0.18) silently
counted TWO invalid taps — see finding 6. With those reclassified as tap-failures (terminal
state = auto fallback, like ROW-4) the honest tap column is the one above. Strictly-as-run,
tap-only, including the invalid taps: 0.27/0.18 with two body-sourced counts — do not quote it.

**Findings (the interesting ones):**
1. **The tap edges auto on COUNTS but LOSES on velocity-loss.** BN-4-0609 is the tell:
   the tap counted 10/10 yet its loss read 7% vs Vitruve's 45% — the tapped left plate
   track is count-right but velocity-wrong, while auto's candidate-verification (lock
   confidence × cadence regularity) had selected a better-quality track (loss err
   1.4pp). **Count-equal ≠ velocity-equal; the verification score is a track-quality
   judge, not just a counting heuristic.** Product implication: feed the user's tap in
   as a PRIORITY CANDIDATE through the same flow-verification scoring — assist, don't
   override.
2. **The static-seed guard is the re-tap UX, working.** 5 of the agent's mis-taps
   (boxes on floor/background/rack post) were caught instantly as `static_track_suspect`
   → re-tap. 17/25 tappable clips landed on the first tap; 3 needed three; 2 needed four.
3. **On matte/dark plates, tap the textured HUB/logo, not the rim.** Flow needs corners;
   a matte bumper face has none (ROW-1-0601 took 4 attempts until the tap covered the
   hub). Extends the texture lesson of roadmap #4.
4. **Auto beat the tap outright on 2 clips:** RDL-1-0610 (a rack post occludes the plate
   every rep — candidate search finds a trackable target a human can't pick from one
   frame; auto 7/8 vs best-tap 6/8) and BN-1-0609 (auto 10/10 vs tap 9/10). ROW-4-0608
   remains UNTAPPABLE (working plates edge-on; the only big disc is a rack decoy —
   re-verified). One-tap is NOT a strict upgrade; it's a complementary candidate source.
5. **The 06-05 lockout-start "mis-taps" still tracked** — flow's near-seed re-centering
   forgives ±100px; the taps that fail are the ones on the wrong OBJECT or wrong TEXTURE,
   not slightly-wrong positions.
6a. **Post-audit re-tap attempts (all failed honestly — these clips have NO valid frame-0
   tap):** RDL-1/2: at frame 0 the working plate is visually FUSED with the lifter's
   thighs (which is exactly why the body-lock happened) and the "obvious" plate disc is
   through-the-rack background (re-tap → static guard). ROW-2-0608: a CORRECT tap on the
   frame-0 plate goes static — dark iron gives flow no texture (re-confirms roadmap #4);
   the v1 "9" survived only because its mis-placed box sat in the plate's mid-rep sweep
   zone. **Product idea this motivates: TAP-ON-ANY-FRAME** — let the user tap the plate at
   its clearest moment and track forward+backward (pairs naturally with roadmap #5
   non-causal trajectory optimisation); the frame-0 constraint is what makes these clips
   untappable, not the plates themselves.
6. **⚑ The BODY-LOCK trap — a mis-tap the static guard CANNOT catch (lifter-caught).**
   The agent's RDL taps landed on the lifter's hip; the hip hinges at exactly rep cadence,
   so the track has high lock-confidence, regular cadence, healthy y-span — it passes the
   static guard AND would pass flow-verification scoring, and it produced plausible counts
   (6/8, 8/8) with meaningless bar-velocity. **Caught only by the lifter reviewing the
   tracked-overlay frames** ("that's my butt, not the plate"). Three consequences:
   (a) the tap-confirm UI must show WHAT is being tracked (overlay playback), not just a
   count — the human review IS the verification layer for body-locks; (b) a cheap
   programmatic guard exists to build: no plate-circle detectable at/near the locked
   target = `no_plate_at_lock` flag (the hip has no rim); (c) same audit found the
   ROW-2-0608 tap was misplaced at frame 0 (background person) and only recovered because
   flow snapped to the plate sweeping through — a count right by luck — and SC-1's miss is
   late-set DRIFT off the dumbbell (~t=20s), which also explains its corrupted loss
   (51% vs 27%): drift, not segmentation, is SC-1's real problem.

## Roadmap — to genuinely best-in-class

Ranked by user-visible failure. Each is additive behind the existing seams.

1. **Distractor rejection (mirrors / multiple plates / bystanders).** Re-acquire has
   a size+proximity guard, but there's no first-class "which candidate is the real
   load" model. Add motion-coherence + lane/size priors (the `PlateTracker` DP idea)
   to the flow re-acquire and the auto-seed.
2. **Scale, properly.** Plate-diameter *detection/classification* (bumper vs iron vs
   hex vs change plate — stop hardcoding 0.45 m), and a real **plate-vs-anthro
   cross-check** (the seam exists; needs the pose pass wired + a disagreement flag).
   This is what fixes the velocities, not just flags them.
   - **Seed-independent scale (confirmed sharp edge, 2026-06-04).** The scale detector's
     Hough radius search is locked to ±20% of the *seed box*, and the scale lane is derived
     from the seed too. A too-small seed under-sizes the plate → m/px (hence velocity AND
     ROM) inflate by the same factor. Verified on the squats: a too-small seed gave 1.40/1.75
     (plate 60/54 px); sizing the seed to the true plate (98/94 px) dropped it to **0.91/0.92**
     vs Vitruve 0.80/0.79. SmartBarbell sizes the plate itself, so its velocity was fine even
     where its rep *count* failed.
     - **Attempted fix + outcome (`robust_scale`, EXPERIMENTAL, default-OFF).** Built a wide,
       seed-independent calibration scan (`FlowTracker._calibrate_scale`) and stress-tested
       three circle-selection rules across the corpus. None is robust across plate-size ×
       clutter: *nearest-to-centre* grabs the concentric hub (misses the squat); *all-pooled
       median* is dragged down by background circles (broke device-grade IB-1 0.44→0.79 and
       the rows); *largest-near-centre* preserved IB-1/ROW-1 but broke ROW-2 and over-sized
       the deadlift, and still missed the squat. Conclusion: simple Hough auto-sizing isn't
       safe to default-on. Left as an opt-in. **The durable fix is roadmap #6 (a learned
       plate detector) or a user-confirmed plate size** — that's what makes scale truly
       seed-independent. Reliable path today: a well-sized seed (board uses these).
     - **BUILT (2026-06-04): user-confirmed plate + camera angle (`plates.ScaleSpec`,
       wired via `VideoConfig.scale_spec`).** Real-world diameter from the *largest* plate
       (stacking → outer rim) + bumper/iron; camera angle gates the rest — **side** =
       diameter valid, full confidence; **diagonal** = ellipse + out-of-plane arc → reduced
       confidence + flags `needs_anchor` (ADVISORY — the rim anchor stays opt-in: validated
       that a blanket diagonal→anchor helps the row arc but SPLITS the deadlift 2 reps into 7,
       so angle alone can't gate it); **head-on** = plate edge-on → invalid → falls back to
       anthropometric, else flagged relative-only. Confidence = plate-certainty × angle
       factor. Pixel diameter still from the seed (the user adjusts that in-app).
       ⚑ Angle/plate/speed vary PER CLIP (deliberately) — `scale_spec` is a per-clip input,
       never a per-lift-day constant. `cv_eval.py --scale` runs the board angle-aware.
       This is the practical scale fix; the learned detector (roadmap #6) removes the seed.

## App layer (human-in-the-loop)

The Python side exposes proposals + editable boundaries; the app makes them correctable
(the project's core principle — surface confidence, let the human correct, learn from it):

- **Plate confirm/adjust** — show the detected plate box + inferred size/kind; one tap to
  correct. This *is* the robust "pixel measurement" — more reliable than any auto-detector.
- **Draggable rep start/stop markers on a SmartBarbell-style time series**, editable while
  scrubbing the clip (so a deadlift rep starts on the pull, not on pulling bar slack). This
  is the manual editor from `sources-and-fusion.md`; the segmenter already emits per-rep
  boundaries + `partial_rom`/confidence for it to bind to.
- **Auto camera-angle** (follow-up) — infer side/diagonal/head-on from the plate's ellipse
  aspect ratio to pre-fill the manual pick.
3. **Viewpoint / angle.** Camera-angle estimation + out-of-plane correction (the
   rim-anchor patches only the row-arc symptom). At minimum, detect oblique views and
   widen confidence.
4. **Adaptive tracker selection.** Pick/weight trackers by *measured* scene
   conditions (square-on plate → plate; side-on isolation → pose; cluttered → flow)
   instead of the static flow+pose ensemble. **Field finding (2026-06-08/09):**
   FlowTracker fails on *low-texture* plates — a smooth **dark iron** plate (rows
   060826; heavy bench 20260609 BN-2/3/4) gives flow no corners, so it tracks the
   background and reports `static_track_suspect`. The **detector** family handles it
   (PlateTracker got 7/10 on a row where flow got 0). So: when flow comes back
   `static_track_suspect`, **auto-fall back to PlateTracker/CSRT** (gated like
   `auto_occlusion`, so it can't regress textured-plate clips). Texture, not just
   clutter, should drive tracker choice. (Bumpers = high texture/colour → flow is
   fine; dark iron = detector.)
7. **Bilateral plate tracking (track BOTH bar ends).** ⚑ *2026-06-11 assessment: currently
   UNVALIDATABLE on this corpus — its showcase failure (BN-1-0609 edge-clipping, SB 3/10) is
   already exact via candidate-gen picking the visible end, and every clip with two visible
   plate faces is exact too; the remaining errors are front-view/dark-iron clips where the
   second plate is also edge-on. Build it when a clip exists that exhibits single-end failure
   with the other end visible (validation discipline: no feature the board can't judge).*
   SmartBarbell tracks the plate on
   *each* end of the bar when both are in frame (the red + green boxes) and uses one if
   only one is visible — observed 2026-06-09. We should match and exceed this: track both
   plate ends and **fuse** them. Wins: (a) redundancy — if one end clips the frame,
   occludes, or loses texture, the other carries (directly addresses the 20260609-BN-1
   "plates clipping the right edge" failure and SmartBarbell's own set-1 3/10); (b)
   **averaging the two ends cancels bar tilt / asymmetric whip** and halves independent
   tracker jitter → a cleaner trajectory and better rep segmentation; (c) a left-vs-right
   *disagreement* is a free quality signal (bar tilt, or one end mis-tracked). Cheap to
   prototype: run the existing tracker on two seeds and average the vertical signal.
5. **Global (non-causal) trajectory optimisation.** We have the whole clip — smooth
   forward+backward, multi-hypothesis, and exploit **intra-set consistency** (reps
   share ROM/cadence/path; outliers are repairable) before committing reps.
6. **Better auto-seed.** A learned plate/bar-end detector to replace the
   largest-blob heuristic.

## Validation discipline

- Extend `CLIPS` in `cv_eval.py` for every new clip with a ground-truth count.
- **Score by lift priority** (learning #15). Main lifts (squat/bench/deadlift) must be right
  first; rows/RDLs matter less; accessories (skull crushers, DB) least. `--auto` reports both an
  unweighted and a **lift-weighted** mean|err| (`lift_weight()`: 1.0 / 0.5 / 0.25). Judge changes
  on the weighted number — **never trade a main-lift regression for an accessory gain.**
- Each robustness change must **not regress** the healthy clips (SQ-1) while
  improving the hard ones — the auto-fallback pattern is the template: opt-in or
  auto-engaged, never a global default that taxes the easy case.
- `pose` clips (e.g. SC-1, hex DB side-on) need MediaPipe + a one-time model
  download (network); they exercise the equipment-free path and the anthro scale.
