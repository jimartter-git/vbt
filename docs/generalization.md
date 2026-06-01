# Generalizing meVBT video to any lift

> Decision record. Question that prompted it: *"What do we do when I want CV velocity
> for a tricep pushdown? One generalized algorithm keying on the wrist/hand, or 2–3
> different algorithms per lift type?"*

**Answer: one pipeline, one shared back-end, a small set of interchangeable
front-ends.** Not an algorithm per lift. This doc is the taxonomy so we extend by
*registering a tracker + picking a scale strategy*, never by forking the spine.

## The pipeline only forks at two seams

```
FrameSource ─▶ Tracker ─▶ Scaler ─▶ Kinematics + Segmentation ─▶ reps
 (decode)      WHAT we    HOW px→m   SHARED, exercise-agnostic    (mevbt_cv)
               follow                 (velocity, ZUPT, rep split,
                                       per-rep confidence, fusion)
```

A pushdown rep and a deadlift rep are the *same* downstream problem: position-vs-time
→ segment concentric phases → velocity per rep. So **kinematics + segmentation +
dataset contract + fusion are shared and never change.** Only **Tracker** (what to
follow) and **Scaler** (how to get meters) vary — and both are already swappable seams
(`track.py`, `kinematics.py`). Adding a lift = config, not a new codebase.

## Tracker families — two, both emit the identical `(t, cx, cy)` trajectory

| Family | Follows | Best for | Seed UX | Cost |
|---|---|---|---|---|
| **Implement tracker** — `FlowTracker` (default), `PlateTracker`, `CSRTTracker` | a rigid loaded object: bar, plate, dumbbell, cable handle, smith bar | barbell · dumbbell · smith · cable (when handle/stack visible) — best absolute accuracy | tap the plate/bar once | classic CV, cheap, on-device-ready |
| **Pose tracker** — `PoseTracker` (new, prototype) | a named body landmark: wrist, elbow, hip, shoulder | *everything*, equipment-free: pushdown, pull-up, dip, machines, bodyweight | **none** (landmarks are automatic) | a pose model (MediaPipe), heavier |

Downstream cannot tell which produced the trajectory — that's the whole point. Pose is
the **universal fallback**: it needs no seed box (strictly better onboarding than the
barbell path) and covers exercises that have no trackable implement.

So generalization in tracking = **one approach (point/region/pose tracking), different
seedings** — not a zoo of algorithms.

## Scaler menu — px→m is where the small "flavors" live (a short list, not per-lift)

The hard part of generalizing isn't tracking, it's **scale**. The menu:

| Scale source | Reference length | Works when |
|---|---|---|
| `PlateDiameterScaler` (now) | bumper plate Ø (0.45 m) | a plate faces camera |
| `EllipseScaler` (planned, see off-angle finding) | plate *outer* ellipse major axis | any plate, **any angle** (foreshortening-invariant) |
| **plate height / bar length / dumbbell length** | known implement dimension | that implement is in frame |
| **weight-stack plate height** | stack plate pitch | cable / selectorized machines |
| **pose anthropometrics** | a body segment (forearm ≈ 0.146·H, upper-arm ≈ 0.186·H) from user **height** | pose is tracked — the skeleton *is* a ruler |

**Pose is a two-for-one:** the same landmarks give us the tracker *and* a metric scale
(if we know the user's height). That's why the equipment-free path is more self-
contained than it first looks.

## The one real subtlety: hand velocity ≠ load velocity on arcs

VBT velocity is the *load's* velocity.
- **Barbell:** bar = load. Trivial.
- **Straight pushdown:** cable is ~vertical, so the wrist's **vertical** displacement ≈
  weight-stack displacement (≈1:1). Tracking wrist-y works.
- **Cable curl / lateral raise:** the hand swings on an **arc**, cable angle changes —
  hand speed and load speed diverge. Don't trust raw hand speed here.

Universal fix for cable/machine work: **track the weight stack** when visible (known
plate pitch → scale; moves purely vertically → a gift for ZUPT). Else track the handle;
else accept the wrist as a proxy *only* on near-linear movements, and flag lower
confidence.

## Why the bar is lower than "match SmartBarbell on a deadlift"

Our headline signal — **velocity *loss*** — is **relative**. A pose-based wrist tracker
with imperfect *absolute* scale still gives a clean loss curve (rep 8 is 30% slower than
rep 1) as long as it's *consistent rep-to-rep*. That's the fatigue proxy we sell. So
"support a pushdown" needs **consistent relative velocity + a reliable rep count** —
both of which pose handles — not perfect absolute m/s.

## The multimodal kicker — roles flip for isolation work

On a tricep pushdown the **Apple Watch is strapped to the moving wrist** — a direct IMU
of the exact landmark pose is estimating. So for cable/isolation work the **watch becomes
primary** and video-pose the validator (opposite of the barbell case, where the wrist
only loosely tracks the bar). They fuse naturally because they measure nearly the same
point. Our confidence-weighted fusion was built for exactly this source-reweighting.

## Decision matrix — what each lift uses (no new algorithms, just seam choices)

| Lift | Tracker | Scaler | Notes |
|---|---|---|---|
| Deadlift / squat / bench / press | `FlowTracker` | plate (→ `EllipseScaler` off-angle) | implement = load; best accuracy |
| Dumbbell work | `FlowTracker` | dumbbell length | same as barbell, different ref length |
| Smith / leg press | `FlowTracker` | bar/sled dimension or stack | linear track; clean ZUPT |
| **Cable pushdown / row** | `PoseTracker` (wrist) **or** stack tracker | stack-plate pitch / anthropometric | wrist-y ≈ stack-y if cable vertical; watch = primary |
| Cable curl / lateral raise | `PoseTracker` (wrist) + caution | anthropometric | arc → hand≠load; rely on watch + relative VL |
| Pull-up / dip / bodyweight | `PoseTracker` (hip/shoulder) | anthropometric | no implement at all |

## Bottom line

One spine. One kinematics/segmentation core. Two tracker families behind one interface.
A short scale menu. Extending to a new lift is **"register a tracker, pick a scale
strategy"** — exactly the payoff the swappable-seam architecture was chosen for.
`PoseTracker` (next to this doc) is the first proof: equipment-free, no seed, same
`(rep, velocity, ROM, confidence)` output, straight into the dataset and fusion.
