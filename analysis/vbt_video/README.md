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
| Track | `Tracker` | **`PlateTracker`** (default) · `CSRTTracker` (region, seeded) | **pose/joint** (equipment-free) · learned **point tracking** (CoTracker) · **segmentation** (SAM) |
| Scale | `Scaler` | `PlateDiameterScaler` (0.45 m) | bar length · reference object · auto-cal |
| Kinematics + segmentation | shared | `trajectory_to_reps` | same logic family as the watch/WL paths |

### `PlateTracker` — the blur-robust default

A plate clip from a phone at the foot of the bench is *hard*: heavy motion blur on
the fast reps, the plate clipping the frame at lockout, and a gym background full of
**other same-size, same-gray circles**. A frame-by-frame circle detector (Metric/WL)
and a region tracker (CSRT) both fail here — CSRT drifts off the blurred plate (0 reps);
naive nearest-circle locks onto a background plate-stack for dozens of frames.

`PlateTracker` is two passes:
1. **Detect** — Hough circles per frame, restricted to the plate's vertical *lane*
   (an x-band seeded from the bbox) and to a consistent radius. Often returns the plate
   *and* distractors. (Hough's vote threshold scales with radius, so it generalises
   across plate sizes.)
2. **Choose a path** — a global **min-acceleration dynamic program** picks one candidate
   per frame (skipping blurred frames by interpolation). The bar moves smoothly; hopping
   onto a background circle and back costs a big acceleration spike, so the DP won't —
   *even though a stationary distractor looks "smooth" to a nearest-neighbour tracker.*
   **Motion-coherence is the discriminator appearance can't give us** — plate and rack
   circles measure the same gray (verified on our clip: plate 93–105, distractors 80–110).

On the incline-bench set `20260528-IB-1` (front camera, 30 fps, motion-blurred), this
recovers the per-rep **velocity-loss curve in the right shape and ballpark** beside the
four commercial tools — reading low by a roughly **constant ~0.06 m/s offset** (the
*calibratable* signature, not a slope error). On that same clip Metric undercounted to
5 reps and WL needed manual circle placement. The honest gaps (early-rep magnitude lost
to blur; the terminal rep) are flagged by a low `track_confidence` and are exactly what
fusion with the watch IMU is there to cover.

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
python -m pytest analysis/tests/test_video_pipeline.py -q   # synthetic disc, in-memory + mp4 round-trip
```

## Score a real clip against the other tools

```bash
# seed the plate from frame 0 (X,Y,W,H); --band X0,X1 fixes the vertical lane
# (keeps the DP off far-background circles). --auto-seed works on clean clips.
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
