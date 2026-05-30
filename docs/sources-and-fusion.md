# Sources & Fusion — the north-star design

> Status: **vision doc, not yet built.** The PoC (watch IMU + ZUPT + Vitruve
> calibration for deadlift) is Phase 0. This captures where we're headed so the
> abstractions we lay down now don't fight it later. Build it in the bite-sized
> phases at the end.

## Guiding principle: best effort, always

The product's value is **robustness through graceful degradation**. Any subset
of sensors — down to a single noisy wrist — should still produce a defensible
answer. We never refuse; we estimate and we report *confidence*.

The trick that makes this work: **the learned rep-shape prior is itself an
always-present "source"** that gets *stronger over time*, while physical sensors
come and go. Every rep/set estimate is a confidence-weighted blend of
(whatever sensors fired this set) + (the prior). As sensor quality drops, weight
shifts to the prior; as it rises, sensors dominate and the prior just
sanity-checks.

```
clean video + watch  ->  sensors dominate, prior validates
watch only, noisy    ->  sensor weight low, PRIOR carries it
nothing usable       ->  report low confidence, ask the user (active learning)
```

## The sources

Every source implements `VelocitySource` and emits the same shape —
`(rep boundaries, velocity profile, ROM)` — **plus a confidence/quality
signal**. Sources are asymmetric and complementary:

| Source | Measures | Rate | Strengths | Failure modes |
|---|---|---|---|---|
| **Watch IMU** | accel (integrates → velocity) | ~100–200 Hz | always-on, no setup; best on DL/bench | drift; squat = arm noise; wrist ≠ bar |
| **AirPods IMU** (`CMHeadphoneMotionManager`) | head accel/attitude | ~25 Hz | 2nd independent timing/turnaround signal; squat vertical proxy | head ≠ bar; foreground-biased; low rate |
| **Phone video** (Vision) | displacement **directly** | 60–240 fps | drift-free ROM; near-ground-truth; any angle if region-tracked | needs setup/angle; lighting; occlusion |
| **BLE bar device** (Vitruve/Stance) | displacement **directly** | device | accurate, drift-free; calibration ground truth | must strap to bar; barbell-only |
| **HR** (Watch / AirPods Pro 3 via HealthKit) | heart rate | ~1 Hz | rest-recovery, cardio cost context | blind to muscular strain (the whole thesis) |

**Key asymmetry:** video and BLE measure displacement *directly* (no drift); the
IMUs *integrate* (drift). So video/BLE anchor absolute ROM and the IMUs fill
gaps and work with no camera. Each covers the other's failure mode.

## The prior is learned and personal — the flywheel

Cold-start from a population/exercise-class template (canonical shape, tempo
band, ROM range, velocity range). Then refine **per-user × per-exercise** from
their own history *and their manual corrections*. By session 20, the system
knows what *your* deadlift looks like, so even a lone noisy watch stream is
legible. Messy data + strong personal prior = usable.

## Fusion: sources repair each other's primitives

Fusion is not a final-answer vote. Sources are aligned on a **shared timeline**
(rep-index correspondence, refined by cross-correlation) and combined by
confidence — but the bigger win is that they **improve each other's
primitives**:

- Cross-source **turnaround consensus** (watch + AirPods + video agreeing where
  bottom/top is) → cleaner ZUPT zero-velocity anchors → better watch velocity,
  even when the other sources contribute no velocity of their own.
- Drift-free sources **re-scale** the drifting ones (video ROM corrects watch
  double-integration).

This compounds: better boundaries → better velocity → tighter boundaries.

## Rep segmentation: works for *any* lift

Don't assume 1D vertical barbell motion. Two tiers:

1. **Known exercise** → use its specific prior + dominant-motion-axis model.
2. **Unknown / "misc"** (cable pushdown, DB, no plate) → generic **repetitive-
   motion detection**: PCA to find the dominant motion axis, autocorrelation to
   find cadence, segment on the periodic structure. "~8 cycles of a repeating
   movement at ~2 s each."

For uncalibratable lifts, **absolute velocity is often impossible but
relative/trend is not** — and intra-set *relative* decline (velocity loss, tempo
creep, ROM shrink) **is** the fatigue signal. So "any lift" ships real value via
relative metrics; absolute-velocity calibration (Vitruve) is reserved for the
big lifts where the wrist tracks the bar. **Discipline: never report an absolute
m/s we can't back — show relative, and show confidence.**

## Rep plausibility & re-segmentation (the SmartBarbell 2/3 fix)

A rep has a canonical shape (bottom → ascend → top → optional pause → descend →
bottom) and neighbors bound each other (duration, ROM, a *single* turnaround). A
"rep" ~2× its neighbors' duration, or with ROM far off the set median, or with
two velocity sign-changes, is **flagged as implausible**. In a flagged window we
re-segment using whichever source is cleanest there (template match / DTW
against the rep template, or another source's turnaround). Even single-source
logic catches the SmartBarbell merge: that long "top" plateau is too long and
velocity must cross zero inside it.

## Manual editor + active learning

Most apps treat output as final. We don't:

1. **Boundary editor** — drag rep start/end, add/delete a rep, merge/split.
   Immediately re-derives that set's metrics.
2. Each correction is a **label** that refines the per-user prior → next session
   is better. The flywheel.
3. **Confidence-triggered prompts** — when fused confidence is low, *ask*:
   "reps 2–3 look merged — did that happen?" Label exactly the high-value cases.
4. **Define-by-example** — name a new exercise and the editor seeds its prior.

## Per-metric reliability (not just per-source)

Confidence isn't only per-source — it's **per-metric**. Real-set evidence (Metric,
deadlift 330×8): **time-to-peak velocity** trended cleanly and monotonically
(0.8→1.3 s) and was *most decisive on the terminal rep* — exactly where mean
velocity was a disputed mess across apps. **Eccentric power** on the same reps
still threw an outlier (a 614 W rep-7 spike, 2× its neighbours) despite being
purpose-built to de-noise eccentric *velocity* — so even a "robust" metric needs a
trust weight. So:

- Carry a **per-metric trust weight**, not just a per-source one. Lean on clean
  channels (mean velocity, time-to-peak); down-weight noisy ones (peak velocity is
  explicitly noise-prone; eccentric power can still spike).
- **Time-domain fatigue metrics (time-to-peak, tempo) are more robust on grindy
  terminal reps than magnitude metrics (velocity, power)** — confirmed in the
  literature ("time-to-peak is one of the first metrics to deteriorate under
  fatigue"). The terminal reps are the most fatigue-relevant *and* least reliably
  measured. Corroborate: velocity ↓ *and* time-to-peak ↑ is robust when either
  alone is noisy.
- Cross-source velocity error looks like a **roughly constant offset**, not a
  velocity-proportional one (full-text validation + our own Metric≈Stance+~0.045
  data), so calibration can **start as a simple offset/linear fit** — keep a
  velocity term available but verify the Bland-Altman slope first. See
  `vbt-reference.md` §1.

## Confidence in the UX

Always surface it. "5 reps · high confidence" vs "~5 reps · tap to verify."
Honest, and it turns uncertainty into the active-learning opportunity above.

## Architecture seams

```
Sources (VelocitySource + confidence)
  Watch IMU · AirPods IMU · Video · BLE · HR(context)
        │  each emits (boundaries, velocity, ROM, quality)
        ▼
Timeline align  ──►  Fusion (confidence-weighted; turnaround consensus)
        │                         ▲
        ▼                         │
RepSegmenter (prior-aware,   MovementPrior store
 1..N sources, periodicity    (per user × exercise;
 fallback for any lift)        population cold-start)
        │                         ▲
        ▼                         │
Rep plausibility / re-segment     │ labels
        │                         │
        ▼                         │
Per-rep metrics + CONFIDENCE ──► UX ──► Manual editor / active-learning ─┘
        │
        ▼
Rep + fatigue model (velocity loss → muscular strain & recovery)
```

## Phasing (bite-sized → the dream)

- **Phase 0 — done.** Watch capture (HKWorkoutSession + high-rate motion) →
  CSV → phone; offline ZUPT velocity; Vitruve calibration for deadlift.
- **Phase 1.** Confidence on every output; per-user prior (shape/tempo/ROM) for
  the big 3; ship **relative** metrics (velocity loss). De-risk watch-only.
- **Phase 2.** Manual rep editor; corrections feed the prior (flywheel).
- **Phase 3.** Add a 2nd source (video via seeded-region tracking, or AirPods
  IMU); fusion layer + turnaround consensus.
- **Phase 4.** Any-lift generalization: periodicity fallback + "misc" tag.
- **Phase 5.** Full multi-source fusion; confidence-triggered active-learning
  prompts; HR as context into the strain model.
```

## Optional future hardware — the gym "sensor-cam" (parked idea, not committed)

A small, strongly-magnetized wide-angle camera that sticks to a rack/upright and
watches the lift. Whoop-in-spirit: **no screen, no playback, no saved footage** —
frames are consumed on-device by computer vision (velocity, ROM, strain) and
discarded. *It's a sensor, not a camera.*

Why it's compelling:
- **Kills video friction** — ambient capture, no tripod/aiming; installed once per
  station → fixed, known geometry → stable, easy calibration. The "forgiving
  video" problem largely dissolves when the camera lives on the rack.
- **Privacy-by-design is the wedge** — bystanders and gym owners accept a
  no-recording sensor far more than a phone pointed at the room; "it never stores
  video" is a real differentiator and a clean **B2B gym-install** opener.
- **Pairs with the watch (fusion)** — camera = drift-free bar velocity; watch =
  identity + IMU + always-on. The watch handshake also solves *which lifter is
  this?* attribution.

**Placement decides which sensor leads** (one device, flexible form):
- *On a rack / floor / box, angled at you* (the primary idea): the **camera leads**
  — ambient, privacy-first, attach nothing, multi-station.
- *On the bar / plate* (optional "power mode"): an **IMU leads** (Stance-style
  direct kinematics), and the outward camera can add **visual odometry**
  (background optical flow = drift-free displacement) — so the puck **self-fuses
  IMU + vision on-device** to beat integration drift with no external reference.
- Trade-off: bar-mounted is more accurate and trivially attributes to *you*, but
  loses the ambient/attach-nothing/privacy appeal — so lead with the observer,
  offer on-bar as a mode. Either way it's just another `VelocitySource`.

Parked considerations (deliberately not now): edge compute/battery (motion-wake
duty cycle), gym permissioning / theft / multi-user concurrency, a privacy
attestation (tally light / on-device-only proof), and it's **capital-intensive** —
so strictly *later*. The watch + software path de-risks everything first; this is
an option the data + CV stack unlocks, never a dependency.
