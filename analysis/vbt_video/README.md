# meVBT video velocity pipeline

Our own purely-video rep-velocity estimator — built to beat the plate-circle
competitors on *flexibility* (non-round plates, off-angle, low fps) and to slot
into fusion as just another `VelocitySource`.

## Architecture — chosen so we never have to redesign

```
FrameSource ─▶ Tracker ─▶ Scaler ─▶ Kinematics + Segmentation ─▶ reps
 (decode)      (px traj)   (px→m)    (shared meVBT back-end)      (mevbt_cv)
```

Each arrow is a **swappable seam**:

| Stage | Interface | v1 (now) | drop-in later — no downstream change |
|---|---|---|---|
| Decode | `FrameSource` | `PyAVDecoder` (real timestamps, VFR-safe) | any decoder / live camera |
| Track | `Tracker` | **`FlowTracker`** (default) · `PlateTracker` (detector+DP) · `CSRTTracker` · **`PoseTracker`** (equipment-free, prototype) | learned **point tracking** (CoTracker) · **segmentation** (SAM) |
| Scale | `Scaler` | `PlateDiameterScaler` (0.45 m) · `AnthropometricScaler` (pose, height-based) | bar length · reference object · auto-cal |
| Kinematics + segmentation | shared | `trajectory_to_reps` | same logic family as the watch/WL paths |

**Generalizing to any lift** (one spine, swappable front-ends — not an algorithm per
exercise): see [`docs/generalization.md`](../../docs/generalization.md) for the tracker
families × scale-strategy taxonomy and the per-lift decision matrix.

### `FlowTracker` — the default (temporal optical flow; never drops a rep)

A plate clip from a phone at the foot of the bench is *hard*: heavy motion blur on the
fast reps, the plate clipping the frame at lockout, a slow occluded grind on the
terminal rep, and a gym background full of **other same-size, same-gray circles**.

The key lesson: a per-frame **detector has no memory**, so a blurred frame (no edge) or
an occluded grind rep means nothing to detect — you drop reps. A commercial tool like
SmartBarbell doesn't, because it tracks *temporally* — it follows the same patch of
**texture** frame-to-frame and coasts through blur, and it doesn't care *what* the
texture is (plate face, logo, collar, knurling), so it works filmed from in front of or
behind the bar. `FlowTracker` does the same:

- **Flow owns position** — pyramidal Lucas-Kanade on a cloud of feature points,
  integrating the *median per-point displacement* each frame (robust to losing any
  subset). **Forward-backward error culling** (the MedianFlow trick) keeps only points
  that track cleanly round-trip — that's what kills drift, so the cloud holds an entire
  set without re-seeding.
- **The detector owns scale only** — it samples the plate diameter for a robust median
  px→m but **never moves the position** (an unreliable detection that yanks the position
  re-introduces exactly the distractor jumps flow avoids).

On the incline-bench set `20260528-IB-1` (front camera, 30 fps, motion-blurred) this
holds lock for the whole set (**`track_confidence` 1.0**) and recovers **all 10 reps**,
landing on the commercial composite: vs Stance, **rmse 0.033 m/s** (cf. WL 0.024, SB
0.015) with a small ~**+0.027 m/s** constant offset (clean calibration, not a slope
error); velocity-loss 47.1% vs SB 46.3 / Stance 44.4 / WL 46.0. On that same clip Metric
undercounted to 5 reps and WL needed manual circle placement.

### `PlateTracker` — detector + min-acceleration path (the fallback)

When a clip has *no trackable texture* (a plain matte plate, very low light), flow has
no features to follow; `PlateTracker` instead **detects** the plate each frame (Hough in
the seed-derived x-lane, consistent radius) and stitches the detections into a bar path
with a global **min-acceleration dynamic program**: the bar moves smoothly, so hopping
onto a background circle and back costs an acceleration spike the DP won't pay — *even
though a stationary distractor looks "smooth" to a nearest-neighbour tracker*.
**Motion-coherence is the discriminator appearance can't give us** — plate and rack
circles measure the same gray (verified on our clip: plate 93–105, distractors 80–110).
On `20260528-IB-1` it gets 9/10 reps but reads ~0.06 m/s low through the blur (rmse
0.074) — which is why flow is the default and this is the fallback.

### `PoseTracker` — the equipment-free, universal front-end (prototype)

For lifts with **no trackable implement** (cable pushdown, pull-up, machines), follow a
**body landmark** instead of the bar. `PoseTracker` reports a chosen joint's `(t, cx, cy)`
— same `Tracker` contract, so scaling/kinematics/segmentation downstream are untouched —
and needs **no seed box** (landmarks are automatic; better onboarding than the bar path).

It's a **2-for-1**: the same skeleton is both the tracker *and* the metric ruler —
`target_px` is a body segment's pixel length (wrist↔elbow forearm by default), and
`AnthropometricScaler` turns it into m/px from the user's height (forearm ≈ 0.146·H).

```python
cfg = VideoConfig(tracker="pose", landmark="wrist", height_m=1.80)  # no seed needed
reps, meta = VideoVelocitySource(cfg).estimate("pushdown.mp4")
```

MediaPipe is imported **lazily** (heavy; may need a first-run `pip install mediapipe`,
see `requirements-video.txt`) and the landmark provider is **injectable**, so the seam is
tested with a synthetic provider — no model needed in CI. The provider **auto-selects**
MediaPipe's API (modern **Tasks** `PoseLandmarker`, or legacy `solutions.pose`), so it
isn't pinned to an old release.

**Scale is a seam too — independent of the tracker.** `VideoConfig(scale="anthro")` takes
px→m from a body segment (a separate pose pass) while *any* position tracker runs — so you
can keep `FlowTracker` on the plate for robust position yet **never trust a plate diameter
for scale** (rubber/iron/hex/edge-on all break plate-circle scaling; see
`docs/generalization.md` "Field finding (2026-06-01)"):

```bash
python analysis/scripts/analyze_video.py clip.mp4 --set-id S --seed X,Y,W,H \
    --scale anthro --height-m 1.89    # flow position + anthropometric (plate-independent) scale
```
 Two caveats it's built around
(full rationale in `docs/generalization.md`): (1) on **arcing** moves (cable curl) hand
speed ≠ load speed — prefer tracking the **weight stack**, or lean on the watch; (2)
absolute scale is only as good as the height prior — but **velocity *loss* is relative**
and survives a scale error if it's consistent rep-to-rep, which is the signal we sell.
On isolation work the roles flip: the **Apple Watch on the wrist becomes the primary**
source and pose-video the validator — they fuse because they measure nearly the same point.

**Why these specific packages (the "no big redesign" call):**
- **PyAV** for decode, not `cv2.VideoCapture` — it gives true per-frame
  timestamps and tolerates **variable frame rate** (phones record VFR); velocity
  needs real time, not assumed fps.
- **opencv-contrib-python-headless** for vision + trackers — Hough + CSRT/KCF,
  headless so it runs in CI / on a server and maps cleanly to an on-device port.
- **Global motion-coherence, not frame-by-frame circle detection** — the
  differentiator. Metric/WL decide each frame in isolation, so a blurred or 12-sided
  plate breaks them (verified in our dataset). `PlateTracker` commits to the *globally
  smoothest* bar path, so blur and look-alike background circles don't derail it.

The output is the same `(rep, mean/peak velocity, ROM, confidence)` shape every
meVBT source emits, tagged vendor `mevbt_cv` — so it flows into the dataset next
to the commercial tools and into the fusion layer with zero glue.

## Install & test

```bash
pip install -r analysis/requirements.txt -r analysis/requirements-video.txt
python -m pytest analysis/tests/test_video_pipeline.py -q   # synthetic disc/texture, in-memory + mp4
```

## Score a real clip against the other tools

```bash
# seed the plate from frame 0 (X,Y,W,H). --band X0,X1 bounds the scale detector's lane
# (keeps it off far-background circles); --tracker defaults to flow. --auto-seed works
# on clean clips. Swap --tracker plate for a textureless plate, --tracker csrt for region.
python analysis/scripts/analyze_video.py dataset/raw/vcompress_1.mp4 \
    --set-id 20260528-IB-1 --seed 323,163,316,316 --band 295,720 --append
python dataset/tools/compare.py 20260528-IB-1      # mevbt_cv now sits beside SmartBarbell/Stance/Metric/WL
```

Pick a **multi-vendor** set (incline bench or a deadlift) so the per-rep velocity
composite is the ground truth. Keep clips **short + downscaled** (~480–720p, a few
MB) — they reach this environment via git, so size matters. `--band` is an ROI hint
(like the seed): the default is derived from the seed bbox; override it when the
background has same-size circles to the side of the bar path.

## Adding a tracker (the common case)

Implement `Tracker.track(source, seed_bbox) -> Track` in `track.py`, register it in
`pipeline._TRACKERS`, select via `VideoConfig(tracker=...)`. Scaling, kinematics,
segmentation, output, dataset integration, and fusion are untouched.
