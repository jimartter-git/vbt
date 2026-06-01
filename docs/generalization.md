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
| `PlateDiameterScaler` (now) | bumper plate Ø (0.45 m) | a plate faces camera, **square-on** (fragile on thick rubber & off-angle — see field finding) |
| `EllipseScaler` (planned, see off-angle finding) | plate *outer* ellipse major axis | any plate, **any angle** (foreshortening-invariant) |
| **plate height / bar length / dumbbell length** | known implement dimension | that implement is in frame |
| **weight-stack plate height** | stack plate pitch | cable / selectorized machines |
| **pose anthropometrics** (`scale="anthro"`) | a body segment (forearm ≈ 0.146·H, upper-arm ≈ 0.186·H) from user **height** | the lifter's scale segment is visible — **works with ANY position tracker**, not just pose |

**Pose is a two-for-one:** the same landmarks give us the tracker *and* a metric scale
(if we know the user's height). That's why the equipment-free path is more self-
contained than it first looks.

**The Scaler is chosen independently of the Tracker** (`VideoConfig(tracker=..., scale=...)`).
`scale="anthro"` runs a *separate pose pass* purely for the body-segment ruler, so you can
track the plate for robust **position** yet take **px→m off the lifter** — never trusting a
plate diameter. It degrades gracefully to the plate ruler if the lifter isn't in frame.

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

## Field finding (2026-06-01) — plate-scale fragility & the anthro cross-check on rows

One session: **Pendlay rows, 135 lb (submaximal), 10 reps, filmed three ways** (side /
oblique / front), each measured by Stance + SmartBarbell, then by our CV two ways
(`FlowTracker`+plate scale, and pose/wrist). Mean concentric velocity (m/s):

| View | Stance | SmartBarbell | Plate-CV (flow+plate scale) | Pose-CV (wrist, anthro) |
|---|---|---|---|---|
| side | 0.78 | 0.63 | **1.17** (plate ok; flow over-reads) | unreliable (arm occluded) |
| oblique | 0.75 | 0.70 | **1.08** | **0.74** |
| front | 0.74 | 0.65 | **0.99** | **0.72** |

Three takeaways (one set, one lifter — **signal, not proof**; don't read the per-angle
ranking as settled):

1. **Plate-circle scale is fragile by plate *type*, not just angle.** These were thick
   **rubber bumpers**: off-axis the near face, far face, and cylindrical rim read as
   multiple offset circles ("two plates from the wrong angle"); **edge-on** a bumper is a
   fat cylinder, not a line, so the diameter detector grabbed a wrong (small) value — the
   **front scale was ~1.4× off**, and that error alone explained the front over-read
   (re-scaling with the correct px→m collapsed ROM 75→54 cm, onto SmartBarbell's 60).
   We must be robust to rubber / iron / hex; **don't scale off the plate.**
2. **The anthropometric ruler is the plate-independent cross-check** — and it works.
   Pose/wrist with only the lifter's height landed **within ~0.02–0.05 m/s of two
   commercial bar devices** (front & oblique), and the hybrid (`flow` position +
   `scale="anthro"`) reproduced that on the front view. It inherits pose's *visibility*
   limit: great front/quarter-on, **degrades on a pure side view** (arm occluded) — so the
   plate ruler and the body ruler are themselves **complementary; pick by what's visible.**
3. **`FlowTracker` over-reads vertical travel on the row arc (~1.4×) — diagnosed & partly
   fixed.** An on-frame overlay + trajectory instrumentation nailed the cause: *not* discrete
   jumps (jerk-limiting removes ~2% — and a motion/Kalman prior conserves net displacement,
   so it can't fix an amplitude bias) and *not* 2D-correctable (RANSAC affine was a no-op).
   It's a **smooth migration of the face-texture centroid off the plate hub** as the plate
   tilts/occludes against the torso at the top of the pull — an out-of-plane effect a flat
   cloud can't see but the circular **rim** can. **Fix:** a slow position anchor to the
   detected rim centre (`VideoConfig(flow_anchor_alpha>0)`) pulls the side view **1.17 → 0.86**
   (into app range) and is a **no-op on square-on bench** (0.44, rmse 0.033 preserved — so
   not overfitting). Residual gap is **plate-detector-quality-limited** (a robust rim fit is
   the next step), and the lesson stands: an amplitude over-read is fixed by anchoring
   *position to geometry*, never by constraining the *dynamics*.

The complementarity is the fusion thesis in one set: the **plate** track holds where the
wrist is occluded (side), the **wrist** holds where the plate goes edge-on (front).
Neither front-end alone is enough; together they cover each other — exactly the
source-reweighting our confidence-weighted fusion was built for.

## Bottom line

One spine. One kinematics/segmentation core. Two tracker families behind one interface.
A short scale menu. Extending to a new lift is **"register a tracker, pick a scale
strategy"** — exactly the payoff the swappable-seam architecture was chosen for.
`PoseTracker` (next to this doc) is the first proof: equipment-free, no seed, same
`(rep, velocity, ROM, confidence)` output, straight into the dataset and fusion.
