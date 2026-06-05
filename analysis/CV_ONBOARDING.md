# CV onboarding — turning a new video clip into a rep count + velocity

The video twin of `dataset/INGESTION.md`. A fresh session can take a context-free
`.mov`/`.mp4` and run **our** CV (`vbt_video`) on it correctly — without re-deriving
the hard-won gotchas. Read `docs/cv-fusion.md` for the design; this is the runbook.

> ⚑ TRIGGER: a `.mov`/`.mp4` upload (especially with little context) = a lift clip to
> run through our CV and score against ground truth. If it pairs with a `…-VITRUVE.csv`
> or vendor screenshot, file those per `dataset/INGESTION.md` first (so the board has a
> GT count to compare against), then do this.

## Step 0 — environment (a cold web session has none of this)

```bash
pip install -r analysis/requirements-video.txt     # opencv-headless + av (PyAV)
pip install mediapipe                               # ONLY for the pose / forearm path
apt-get install -y libgles2 libegl1                 # headless GL for mediapipe Tasks
# numpy/scipy come from analysis/requirements.txt
```
(If imports fail in a cold session, run the above. A SessionStart hook can automate the
light deps — opencv + av + scipy — so the flow path is ready without manual steps; mediapipe
is heavy and only needed for the pose/forearm path, so install it on demand.)

> Auto-seed: calling `estimate(clip)` with **no seed** now runs `auto_seed_motion` — it picks
> the circle whose **motion** (disc×column) is highest, i.e. the one that actually moves, not a
> static rack plate. It gets ~9/14 of the corpus zero-tap (`cv_eval.py --auto`). It's a heuristic
> bridge to the learned detector (roadmap #6), so for a NEW clip still verify (Step 2) — and if a
> count looks wrong, a manual seed per below is the fix.

## Step 1 — find the WORKING plate, not a decoy  ⚠ THE #1 MISTAKE

The FlowTracker follows whatever you seed. A gym frame is full of **same-coloured,
same-size circles that DON'T move**: rack-STORED plates on the uprights, plates on a
neighbouring bar, mirror reflections. **Seed the plate that is ON THE BAR and MOVES.**

Disambiguate by **motion + colour**, not by eye on frame 0 alone:
- The working plate is usually a distinct bumper colour (here: **blue** 20 kg; rack
  plates were green/grey/yellow). A quick HSV mask on the working colour isolates it
  (`cv2.inRange`, e.g. blue ≈ H 95–130). Take the largest blob → its centre + size.
- **Deadlift**: the working plate is on the floor bar at the BOTTOM of the frame (not
  the rack plates up top). **Bench/squat in a rack**: the working plate is at the BAR /
  the lifter's hands — *lower and more central* than the stored plates behind them.

## Step 2 — VERIFY the seed before you trust any number  ⚠ NON-NEGOTIABLE

Overlay the seed box on 3–4 frames spread across the clip and confirm the **plate moves
through the box** (i.e. the bar travels):

```python
import av, cv2
ctr = av.open(clip); fps = float(ctr.streams.video[0].average_rate)
# draw your seed (x,y,w,h) on frames at t≈0,1,2,3s; eyeball that the plate moves vertically
```
If the plate looks static across those frames, you seeded a decoy — go back to Step 1.

## Step 3 — run the board; honour the SANITY GATES

```bash
python analysis/scripts/cv_eval.py --set <set_id>            # count + mean m/s + conf
python analysis/scripts/cv_eval.py --set <set_id> --scale    # angle-aware px→m
```
Read the result through these gates — **a bad number here is almost always YOUR seed,
not "CV can't do it":**

| Symptom | Meaning | Fix |
|---|---|---|
| **`⚠ STATIC-SEED`** / `reps≈0` at `conf≈1.0` / `y_span_px` tiny | seed is on a **static** object | re-seed onto the moving bar plate (Step 1) — **never** report "CV fail" here |
| `mean` printed with a trailing **`?`** | scale flagged suspect | see Step 4 — count is still usable; don't persist the velocity |
| reps ≈ 2× expected, all tiny ROM | seed too **small** → inflated scale, OR fast-TnG over-segmented | size the seed to the true plate; try `--adaptive` |
| `mean` ≈ 2× Vitruve, count correct | diagonal-plate **ellipse** under-measured by the circular Hough | Step 4 |

The pipeline emits `meta["static_track_suspect"]` — it is the programmatic version of
this gate (added after the 2026-06-05 bench mis-seed; see learning #12 in `CLAUDE.md`).

## Step 4 — tracker & scale decision tree

**Tracker (position):**
- **Standing lifts (DL / squat / row)** → FlowTracker on the plate is best; ALSO run
  `PoseTracker(landmark="wrist")` as an independent cross-check — large clean wrist travel
  makes pose reliable here, and it needs no seed.
- **Supine lifts (bench / skull-crusher)** → FlowTracker on the plate. **Do NOT scale off
  pose here**: the forearm/upper-arm point toward the camera (foreshortened) → garbage
  ruler, and the supine wrist jitters → over-count (the SC-1 hazard). Pose is position-only
  at best on supine work.

**Scale (px→m), in order of trust:**
1. **Plate diameter** (`scale_spec=ScaleSpec(top_plate, kind, angle)`), `--scale` on the board.
   - `side` → clean circle, trusted. `diagonal` → **the circular Hough under-measures the
     elliptical plate** (measures ~minor axis); velocity & ROM inflate ~proportionally
     (2026-06-05 bench: 113 px measured vs ~204 px true vertical axis → ~2× velocity).
     `front`/head-on → invalid, fall back to anthro.
2. **Anthropometric / forearm** (`scale="anthro"`, needs `height_m`) — plate-free, immune to
   plate type/angle. **Great for standing lifts** (DL forearm-scaled velocities landed within
   ~0.1 of Vitruve); **bad for supine** (foreshortening).
3. **Relative-only** — when neither is trustworthy, report velocity *loss* (scale-invariant),
   not absolute m/s.

## Step 5 — record it

1. **Register the clip** in `analysis/scripts/cv_eval.py` `CLIPS`: the verified seed, the
   per-clip `{angle, plate, kind}`, and a note (count vs GT, any scale caveat).
2. **`dataset/raw_files.csv`**: add a `video` pointer with the result.
3. **Set notes** (`dataset/sets.csv`): the CV count vs Vitruve/competitor, and the velocity
   caveat.
4. **Persist `mevbt_cv` velocity rows in `rep_metrics.csv` ONLY when scale is device-grade**
   (today: the 720p side-on clips). Scale-suspect velocities stay OUT of the DB — the rep
   COUNT and the board are the deliverable. (Same honest-velocity rule as the rest of meVBT.)
5. `python dataset/tools/build_db.py`, then commit & push.

## Definition of done
- Count matches (or beats the competitor toward) the Vitruve GT, and you can **show the
  seed tracking the moving plate**.
- No `⚠ STATIC-SEED`; any reported absolute velocity is either device-grade or explicitly
  flagged scale-suspect/relative-only.
