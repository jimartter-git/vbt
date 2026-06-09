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
7. **Bilateral plate tracking (track BOTH bar ends).** SmartBarbell tracks the plate on
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
- Each robustness change must **not regress** the healthy clips (SQ-1) while
  improving the hard ones — the auto-fallback pattern is the template: opt-in or
  auto-engaged, never a global default that taxes the easy case.
- `pose` clips (e.g. SC-1, hex DB side-on) need MediaPipe + a one-time model
  download (network); they exercise the equipment-free path and the anthro scale.
