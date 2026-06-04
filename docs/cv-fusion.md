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
| IB-1 | incline bench, well-filmed | **10** | 10 | 10 | mean 0.44 m/s, **rmse 0.033 vs Stance** — velocity device-grade, scale *not* flagged |
| ROW-1/2/3 | barbell row, side/angle/front 720p | **10/10/10** | 10 | 10/9/10 | conf 1.00, occlusion never engages, scale not flagged |

Hard clips (the robustness wins):

| clip | scene | baseline | **now** | Vitruve | SmartBarbell |
|---|---|---|---|---|---|
| SQ-1 | mirror/rack, low-res | 8 | **10** | 10 | 5 |
| SQ-3 | fast touch-and-go (adversarial) | 4 | **9** | 10 | 3 |
| SC-1 | DB press, hex DB end, side-on | pose 32 | **10** | 11 | — |
| DL-1 | deadlift, bumper, front-quarter | — | **2** | — | 2 (=) |

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
       diameter valid, full confidence; **diagonal** = ellipse + out-of-plane arc → auto-
       enables the rim anchor + reduced confidence; **head-on** = plate edge-on → invalid →
       falls back to anthropometric, else flagged relative-only. Confidence = plate-certainty
       × angle factor. Pixel diameter still from the seed (the user adjusts that in-app).
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
   instead of the static flow+pose ensemble.
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
