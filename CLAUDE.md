# CLAUDE.md — operating manual for this repo

You are working on **VBT**, a multimodal velocity-based-training & muscular-fatigue
platform. This file orients a fresh session: read it, then you can get to work
immediately. Detailed knowledge lives in `docs/` and `dataset/` — this is the map
and the rules.

## What this project is

Estimate rep velocity, range of motion, and per-rep/per-set fatigue from MULTIPLE
sources — phone video, BLE bar devices (Vitruve/Stance), and (the bet) a
smartwatch IMU (Apple Watch) + AirPods. The product thesis: HR platforms (Whoop,
Athlytic) are blind to lifting; by counting every rep and tracking intra-set
**velocity loss** (a validated proximity-to-failure proxy), VBT builds a
*muscular* strain & recovery score they can't. Full vision: `docs/architecture.md`
and `docs/sources-and-fusion.md`.

## Status

- **PoC scaffold** (compiles on a Mac, not yet device-tested): watchOS app
  (HKWorkoutSession + CMBatchedSensorManager → CSV → phone), iOS companion,
  shared `VBTCore` Swift package, Python ZUPT analysis pipeline (`analysis/`,
  tests green).
- **Active phase = data + calibration.** Building a personal multi-vendor
  measurement database (`dataset/`) to quantify cross-tool agreement, calibrate,
  and seed the app's per-user prior. **Vitruve is the established ground-truth
  reference** (since 2026-06-02; `compare.py` auto-prefers it — ~392 rep rows across
  bench/squat/skull-crushers, etc.).
- **⚑ Data ingested through 2026-06-10** (no known backlog): 06-05 BN/DL, 06-08 rows,
  06-09 bench, 06-10 squats/RDLs all in `sets.csv`/`rep_metrics.csv`. (06-10 filed as set-level
  Vitruve averages — the app crashed before per-rep export.) Next upload → follow the ingestion
  + video triggers below.
- **⚑ CV milestone (2026-06-10): out-of-the-box BEATS SmartBarbell on reps and on velocity-loss;
  loses on absolute m/s.** Full current scoreboard (reps · velocity · velocity-loss · one-tap
  vs auto, with the numbers and the honest weak spots) lives in **`docs/cv-fusion.md` →
  "Full scoreboard snapshot (2026-06-10)"**. Headlines: auto/no-tap reps **0.55** vs SB **2.57**;
  velocity-loss **6.2pp** vs SB **9.0pp** (common clips); absolute velocity SB wins (~0.07). See
  learning #14 for what to do next.

## Repo map

| Path | What |
|---|---|
| `README.md` | build/run instructions (XcodeGen, Python) |
| `docs/architecture.md` | system design, the `VelocitySource` abstraction, ZUPT |
| `docs/sources-and-fusion.md` | the north-star: AirPods/video/BLE fusion, learned prior, graceful degradation, manual editor |
| `docs/data-schema.md` | the raw IMU + derived-metric contract |
| `docs/calibration-protocol.md` | watch-vs-Vitruve capture protocol |
| `docs/vbt-reference.md` | VBT science + competitor accuracy/metrics (verified vs PDFs) |
| `docs/generalization.md` | generalizing CV to any lift: tracker families × scale strategies (one spine, swappable front-ends; pose/equipment-free path) |
| `docs/cv-fusion.md` | the standalone video estimator as a best-in-class SmartBarbell competitor: what's built (adaptive gating, occlusion auto-fallback, scale confidence), the `cv_eval.py` scoreboard, and the robustness roadmap |
| `dataset/` | the living multi-vendor measurement DB (+ `dataset/README.md`, `dataset/INGESTION.md`) |
| `analysis/` | Python pipelines: `vbt_analysis/` (IMU ZUPT) + `vbt_video/` (our own CV velocity — PyAV+OpenCV, pluggable trackers, `plates.py` plate+angle→scale, outputs vendor `mevbt_cv`). Board: `scripts/cv_eval.py` (`--scale` = angle-aware). **Onboarding a new clip: `analysis/CV_ONBOARDING.md`** |
| `Watch/` `iOS/` `Packages/VBTCore/` | the Swift app + shared package |

## How to work here (conventions)

- **Branch:** develop on `claude/vbt-watchos-architecture-wu6y8`. Commit with clear
  messages; **push when a unit of work is done** (the container is ephemeral —
  unpushed work is lost). Use `git push -u origin <branch>` with retries.
- **Keep context clean:** 21 research PDFs live on a SEPARATE branch
  `origin/jimartter-git-pdfs` (not ours). Don't read them into your context; if
  needed, extract to `/tmp` and dispatch sub-agents (see git history of
  `docs/vbt-reference.md`).
- **Environment limits:** Linux container, **no Xcode** (can't compile Swift —
  author carefully, flag first-build TODOs). Network often blocks `WebFetch`
  (metric.coach, PMC); `WebSearch` usually works.
- **Don't open PRs** unless asked. **Don't** put the model identifier in commits.

## ⚑ Branch & sync protocol — prevents lost/forked work

The dataset and tools are edited across many sessions; the platform may drop a
fresh session on its own `claude/new-session-*` branch. To never lose or fork work:

1. **One canonical branch:** `claude/vbt-watchos-architecture-wu6y8`. Everything
   funnels here.
2. **On START, sync first.** `git fetch origin --prune`, then fast-forward to
   `origin/claude/vbt-watchos-architecture-wu6y8` before doing anything — build on
   the latest, never a stale base.
3. **On FINISH (and every good stopping point), push to canonical.** If you're on
   an auto-created `claude/new-session-*` branch, **merge/fast-forward it back into
   the canonical branch before you stop** — don't strand work on a side branch.
4. **One session edits `dataset/` at a time.** `sets.csv`/`rep_metrics.csv` are
   append-heavy; concurrent appends from two branches collide. Finish + push before
   opening another session that touches the DB. (To truly parallelize, split by
   concern — e.g. one session only `dataset/`, another only `Watch/` Swift.)

## Key decisions & learnings (don't re-litigate — extend)

1. **One `VelocitySource` abstraction** (in `VBTCore`): every source emits
   `(rep boundaries, velocity profile, ROM) + confidence`. Watch IMU is first;
   BLE/video/AirPods slot in behind it.
2. **ZUPT is foundational.** Velocity = single integration of accel; drift is the
   enemy; reset to ~0 at each rep turnaround. So **rep-boundary detection is
   prerequisite, not optional.**
3. **Confidence is per-rep AND per-metric**, and it's **open white space** — no
   competitor clearly surfaces measurement confidence. Time-domain metrics
   (time-to-peak, tempo) are robust on grindy terminal reps where magnitude
   metrics (velocity, power) get noisy.
4. **Calibration = roughly CONSTANT offset**, not velocity-proportional (verified
   vs full-text papers + our own data: Metric ≈ Stance + ~0.045). Start with an
   offset/linear fit; verify the Bland-Altman slope before adding a velocity term.
5. **Every source is fallible** — they disagree on rep count AND decline shape;
   the fatigue-critical *terminal reps* are the most important and least reliably
   measured. Hence fusion + a learned rep-shape prior + a manual editor.
6. **Deadlift MVT ≈ 0.15–0.20 m/s** (not 0.25). Personalized MVTs live in
   `dataset/priors/`. Prefer personal rolling baselines over fixed velocity zones.
7. **Sourcing discipline:** `docs/vbt-reference.md` marks snippet-sourced vs
   full-text-verified vs unverified. Keep that honesty; verify before relying.
8. First lift target = **deadlift** (wrist tracks bar; clean ZUPT anchors).
9. **Capture conditions vary PER CLIP, by design.** The video corpus is a deliberate
   robustness bench — the lifter switches camera angle, rep speed, distance, and plate
   type *shot to shot* (e.g. the barbell rows were filmed side / diagonal / front as
   ROW-1/2/3). **Never assume a lift-day is uniform.** Angle/plate are per-clip inputs,
   not per-session constants. Confirmed per-clip metadata lives in `cv_eval.py` `CLIPS`.
10. **The px→m scale is a deterministic function of (plate, camera angle), not a guess.**
   `vbt_video/plates.py` `ScaleSpec` (wired via `VideoConfig.scale_spec`): real-world
   diameter = the LARGEST plate's outer rim (stacking → smaller plates are concentric;
   bumper ≈ 0.45 m ≥10 kg, iron is brand-dependent → lower confidence) × camera-angle
   policy — **side** = valid/full conf, **diagonal** = valid but lower conf, **head-on**
   = plate edge-on → invalid → fall back to anthro (body) scale, else flag relative-only.
   Pixel diameter still comes from the seed; the user's in-app **confirm/adjust** of the
   detected plate is that surface (more robust than any auto-detector). `cv_eval.py
   --scale` runs the board angle-aware.
11. **Angle alone cannot gate a trajectory correction.** Auto-enabling the FlowTracker rim
   anchor for any "diagonal" clip helped the barbell-row arc (ROW-2 1.09→0.96) but SPLIT
   the deadlift's 2 reps into 7 (front-quarter view). The anchor stays **opt-in**
   (`flow_anchor_alpha`); `ScaleSpec` only *advises* (`needs_anchor` in meta). The fix is
   per-clip human-in-the-loop, not a blanket rule — same principle as the manual editor.
12. **Seed the WORKING (moving) plate, and VERIFY it — a 0-rep result is a mis-seed, not a
   CV failure.** A gym frame is full of static decoy circles (rack-STORED plates, a
   neighbouring bar, mirror reflections). FlowTracker faithfully tracks whatever you seed,
   so seeding a stored plate yields a flat trajectory → 0 reps **at confidence 1.0** — which
   reads like "CV can't" but means "wrong target" (2026-06-05 bench: first seed sat on the
   rack plates → 0 reps; reseeding the blue BAR plate → 10/10/11, beating SmartBarbell).
   Disambiguate by motion+colour (the working bumper is a distinct colour; deadlift plate is
   on the floor bar, bench/squat plate is at the hands — lower/more central than the stored
   plates behind). **Always overlay the seed on a few frames and confirm the plate moves
   through it before trusting any number.** This is now also a programmatic guard:
   `meta["static_track_suspect"]` + a `⚠ STATIC-SEED` line on the `cv_eval.py` board. Full
   runbook: `analysis/CV_ONBOARDING.md`. (Corollary: pose/forearm scale is great for STANDING
   lifts but useless on SUPINE ones — forearm foreshortens, supine wrist jitters.)
13. **The no-tap AUTO path BEATS SmartBarbell on counts, and the win is CANDIDATE-GENERATION +
   FLOW-VERIFICATION** (2026-06-10). `VideoConfig(tracker="auto")`: `seed_candidates()` proposes
   the top-K MOVING circles (each sized to its rim ELLIPSE — a too-small hub seed makes flow
   over-count), then `_estimate_auto` runs FlowTracker on each and KEEPS the one that holds lock
   with a plausible count (3–18) + most regular cadence; if none holds (dark/low-texture iron,
   hex) it falls back to `DetectTracker` (seed-free track-by-detection) for the COUNT. The
   blocker all along was plate LOCALISATION in clutter (mirror/hex/multiple plates) — a single
   auto-seed picks a decoy; generate several + let flow VERIFY which one is the plate.
   **Fully automatic, no seed, no gym config: mean rep-count err 8.5 → 1.36 → 0.55 vs
   SmartBarbell 2.57; 19/22 within ±1 vs SB 13/21.** Generalises (Equinox hex+mirror, Westwood
   bumpers, travel gym, all angles/fps) — the fix is METHOD, not a gym/colour profile (every
   single-method/profile idea — periodicity/motion-model/color/bilateral/twin-pair/PCA —
   plateaued at ~2.5). Board: `python analysis/scripts/cv_eval.py --auto`. Profile-first if
   `plate_color` set; `ColorPlateTracker` is a fallback, not the strategy. ONE-TAP (seed→flow)
   also excellent. **VELOCITY also beats SB
   on the fatigue signal:** velocity-LOSS |err vs Vitruve| 5.7pp (ours) vs 9.4pp (SB) on the
   clips where the fusion reports a reliable velocity — it ABSTAINS (count-only, `velocity_
   reliable=False`) on detect-fallback (dark-plate) clips rather than report a confident-wrong
   number (detect velocity is jittery; flow velocity is trusted). Absolute m/s stays scale-
   suspect at 440px (roadmap #2 ellipse scale / HD clips); velocity-LOSS is scale-invariant and
   is the win. Benchmarks: `cv_eval.py --auto` (counts), `vel_eval.py` (velocity-loss).

14. **Where the goal stands + the highest-leverage next fix (2026-06-10).** Verified, full corpus,
   no per-clip cheating (auto passes only the clip path — `seed=None`, no gym/plate/angle/color
   hint; GT/SB are scoring-only). Full tables: `docs/cv-fusion.md` → "Full scoreboard snapshot
   (2026-06-10)". (a) **Reps: WON** — auto/no-tap **0.55** vs SB **2.57** (one-tap/best-seed 0.36).
   (b) **Velocity-LOSS (the fatigue signal = the product thesis): WON** apples-to-apples **6.2pp**
   vs SB **9.0pp** on the 11 common clips; SB's tell is *flattening the fatigue curve* (SQ-3:
   Vitruve 30%, SB 2.4%, us 26%). (c) **Absolute m/s: OPEN — SB wins** (~0.07; ours ~2× on
   fast/diagonal-bumper low-res, but **velocity/angle-dependent** — slow heavy 06-09 benches scale
   EXACTLY, BN-3 0.33=0.33). **ONE-TAP vs AUTO:** the tap only helps by fixing auto's *over-counts*
   on clean clips; on dark iron a real manual-seed search reproduced auto on 6/7 (candidate-gen
   already finds the seed a human would tap); and on the dead-front row a naive tap *hurts* (the
   big disc is a rack decoy, working plates are edge-on → detect/auto is best — re-confirms #12).
   **⚑ Highest-leverage fix = the near-failure over-count.** The clips we over-count (BN-2/BN-4
   0609 → 11/12) are the SAME clips whose velocity-loss is wrong — one phantom rep at the grindy
   lockout corrupts the loss formula. It's a *segmentation* problem (lifter racks/drifts at
   near-failure lockout), needs no torch/HD, and tightens BOTH counts and loss on the heaviest
   sets. **Options for absolute m/s** (all gated/declined): HD clips (user declined — apples-to-
   apples on low-fi is the standard), or a **learned plate-sizer** for consistent rim measurement
   (**no torch/sklearn in this container** → not buildable here now; classical Hough auto-sizing
   already proven unsafe to default-on, roadmap #2). Don't re-run the rejected single-method seed
   ideas (#13). The user wants GENERALIZATION, not gym/plate-color overfitting (06-05 colored
   bumpers were a one-off travel gym; Westwood=bumpers, Equinox=bumpers or iron hex are the
   regulars) — keep the method gym-agnostic.

## ⚑ Video trigger — READ THIS

**If the user uploads a `.mov`/`.mp4` (especially with little context) — it's a lift clip
to run through OUR CV (`vbt_video`) and score against ground truth.** Follow
`analysis/CV_ONBOARDING.md` end-to-end: install CV deps (Step 0), **find the moving bar
plate not a decoy + VERIFY the seed** (Steps 1–2, learning #12), run `cv_eval.py` and honour
the sanity gates (Step 3), pick tracker/scale (Step 4), then register the clip + record
findings (Step 5). If a `…-VITRUVE.csv`/vendor screenshot came with it, file those via the
dataset ingestion trigger first so the board has a GT count to beat.

## ⚑ Ingestion trigger — READ THIS

**If the user sends a screenshot or a data file (`.txt`/`.csv`) — especially with
little or no context — assume it is a VBT measurement to add to `dataset/`.** Do:

1. **Identify the vendor** from the UI/format (recipes in `dataset/INGESTION.md`):
   Stance, SmartBarbell, Metric, WL Analysis, or Vitruve.
2. **Prompt for the metadata you need** to build the `set_id` and link comparables.
   Use this template — fill what you can infer, ask for the rest:

   > To file this correctly I need: **date** · **lift** (squat/bench/deadlift) ·
   > **load** (e.g. 330 lb) · your **set #** that day · your **RPE** (optional) ·
   > and **which other tools** you recorded this same set with (so I link them
   > under one `set_id`). I read this as **<vendor>** showing **<N reps>** — confirm?

3. **Transcribe / import** per `dataset/INGESTION.md` (column→metric mapping, unit
   canon kg/cm, the SmartBarbell phantom-row + `true_rep` gotchas).
4. **Add to the DB:** append the `sets.csv` row + `rep_metrics.csv` rows (or run
   `tools/wl_import.py`), then `python tools/build_db.py` and
   `python tools/compare.py <set_id>` to sanity-check, then commit & push.

Never invent metadata — ask. Never compare across vendors on `rep_index`; align on
`true_rep`. See `dataset/INGESTION.md` for the full step-by-step.
