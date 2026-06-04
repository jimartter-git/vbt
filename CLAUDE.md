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
  and seed the app's per-user prior. A Vitruve (ground truth) is arriving.

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
| `analysis/` | Python pipelines: `vbt_analysis/` (IMU ZUPT) + `vbt_video/` (our own CV velocity — PyAV+OpenCV, pluggable trackers, outputs vendor `mevbt_cv`) |
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
