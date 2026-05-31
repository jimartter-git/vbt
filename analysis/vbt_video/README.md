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
| Track | `Tracker` | `CSRTTracker` (region, seeded) | plate detector · **pose/joint** (equipment-free) · learned **point tracking** (CoTracker) · **segmentation** (SAM) |
| Scale | `Scaler` | `PlateDiameterScaler` (0.45 m) | bar length · reference object · auto-cal |
| Kinematics + segmentation | shared | `trajectory_to_reps` | same logic family as the watch/WL paths |

**Why these specific packages (the "no big redesign" call):**
- **PyAV** for decode, not `cv2.VideoCapture` — it gives true per-frame
  timestamps and tolerates **variable frame rate** (phones record VFR); velocity
  needs real time, not assumed fps.
- **opencv-contrib-python-headless** for vision + trackers — CSRT/KCF today,
  headless so it runs in CI / on a server and maps cleanly to an on-device port.
- **Region tracking, not circle detection** — the whole differentiator. A seeded
  region tracker doesn't care that a plate is 12-sided or off-axis, which is
  exactly where Metric/WL's plate-circle scaling broke in our dataset.

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
# auto-seed the plate (or pass --seed X,Y,W,H from frame 0)
python analysis/scripts/analyze_video.py CLIP.mp4 --set-id 20260528-IB-1 --auto-seed --append
python dataset/tools/compare.py 20260528-IB-1      # mevbt_cv now sits beside SmartBarbell/Stance/Metric/WL
```

Pick a **multi-vendor** set (incline bench or a deadlift) so the per-rep velocity
composite is the ground truth. Keep clips **short + downscaled** (~480–720p, a few
MB) — they reach this environment via git, so size matters.

## Adding a tracker (the common case)

Implement `Tracker.track(source, seed_bbox) -> Track` in `track.py`, register it in
`pipeline._TRACKERS`, select via `VideoConfig(tracker=...)`. Scaling, kinematics,
segmentation, output, dataset integration, and fusion are untouched.
