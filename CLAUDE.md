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
- **⚑ CV milestone (2026-06-11): the near-failure over-count is FIXED — reps AND velocity-loss
  tightened together; absolute m/s still open.** Current scoreboard lives in
  **`docs/cv-fusion.md` → "Full scoreboard snapshot (2026-06-11)"**. Headlines: auto/no-tap reps
  **0.32** (lift-weighted **0.25**) vs SB 2.57/2.54, 21/22 within ±1, every bench+squat exact;
  velocity-loss **3.2pp** vs SB **9.0pp** (common clips). Loss now has ONE canonical definition
  everywhere (`vbt_analysis/metrics.py`). Absolute velocity unchanged (SB wins ~0.07; gated —
  see #14). Gate design rules: learning #16.

## Repo map

| Path | What |
|---|---|
| `README.md` | build/run instructions (XcodeGen, Python) |
| `REFERENCES.md` | tiered research leads: Achermann 2023 (Apple Watch VBT validation), **Wojtek120 open-source IMU VBT** (Madgwick+ZVU), Core Motion, Madgwick AHRS, Renner 2024 benchmarks |
| `docs/architecture.md` | system design, the `VelocitySource` abstraction, ZUPT |
| `docs/sources-and-fusion.md` | the north-star: AirPods/video/BLE fusion, learned prior, graceful degradation, manual editor |
| `docs/data-schema.md` | the raw IMU + derived-metric contract |
| `docs/calibration-protocol.md` | watch-vs-Vitruve capture protocol |
| `docs/vbt-reference.md` | VBT science + competitor accuracy/metrics (verified vs PDFs) |
| `docs/generalization.md` | generalizing CV to any lift: tracker families × scale strategies (one spine, swappable front-ends; pose/equipment-free path) |
| `docs/cv-fusion.md` | the standalone video estimator as a best-in-class SmartBarbell competitor: what's built (adaptive gating, occlusion auto-fallback, scale confidence), the `cv_eval.py` scoreboard, and the robustness roadmap |
| `docs/video-storage.md` | HD masters too big for git → live in Cloudflare R2 (`vbt-video`); repo keeps `dataset/raw/manifest.csv` pointer + `vbt_video/clip_store.py::resolve_clip()` (local→cache→download). Phone upload (Safari / Worker+Shortcut) + the live-app direction |
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
   **⚑ Highest-leverage fix = the near-failure over-count (FIXED 2026-06-11 → see #16:
   both clips now exact, loss errors 3.3/1.4pp).** The clips we over-count (BN-2/BN-4
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

15. **Lift priority — get the MAIN lifts right first; weight the backtest accordingly.** Product
   priority: **squat / bench / deadlift = main (must nail)** > **rows / RDLs = secondary** >
   **isolation / accessories (skull crushers, DB press) = least**. Full fusion (watch + video +
   human editor) will eventually handle everything, but when scoring CV approaches the main lifts
   matter most — a squat regression costs more than a skull-crusher one. Encoded in
   `cv_eval.py::lift_weight()` (main=1.0 / secondary=0.5 / accessory=0.25, gentle + tunable);
   `--auto` now prints BOTH **unweighted** (continuity) and **lift-weighted** mean|err|. On the
   2026-06-10 board it slightly *widens* our lead (ours 0.55→**0.48** weighted; SB 2.57→2.54) —
   our residual errors cluster in the down-weighted rows while SB's big misses are on the main
   lifts (SQ/DL). When judging a new CV change, prefer the **lift-weighted** number; never trade a
   main-lift regression for an accessory gain.

16. **Rep-plausibility gate (2026-06-11): terminal phantoms are POSITION-anomalous — and the
   three ways NOT to build the gate (each validated by a real failure; don't re-litigate).**
   Rack-in / put-down / lockout-drift phantoms don't anchor at the set's own bands: they start
   off the bottom band or end far above the top band by **0.68–3.3×ROM** (neighbor-tolerant)
   while every real trailing rep on the corpus sits **≤0.33×ROM** — wide separation, thresholds
   insensitive ±20%. Implementation: `kinematics._plausibility_gate` (+`apply_plausibility`),
   `VideoConfig.plausibility_gate` default OFF (manual/one-tap paths byte-identical); the AUTO
   path applies it to flow/profile picks. The three constraints: (a) **post-selection only** —
   gating candidates BEFORE flow-verification changes their counts/cadence scores and flips the
   pick onto a decoy (BN-4 12→3); (b) **trailing-strip only** — the phantom family is terminal
   by mechanism; judging leading/mid reps positionally kills real reps on distorted-geometry
   clips (dead-front ROW-4 8→6); (c) **abstain on position-incoherent tracks**
   (MAD(start)>0.25×ROM) **and never gate the detect path** — position plausibility needs
   position-trustworthy tracks (dark-iron flow resonator ROW-1-0608: 10→0 without this).
   Result: reps 0.55→**0.32** (weighted 0.48→**0.25**), loss 6.2→**3.2pp**; no clip worse.
   Same session: **ONE canonical velocity-loss** (`vbt_analysis/metrics.py::velocity_loss_pct`,
   best→mean-of-last-2, <3 reps=NaN, phantoms excluded) replaced FOUR divergent formulas
   (vel_eval / dataset compare best→last / velocity.py best→min / Swift best→min — mirrored in
   Swift `SetSummary`, keep in lock-step). Measured: k=2 window beats k=1 (3.97 vs 5.57pp
   weighted); excluding partial_rom reps from the window is noise (<0.2pp) → off. compare.py's
   printed VL re-baselined (was best→last). Residual known misses, all honest limits: DL-3-0605
   +1 (11th candidate positionally identical to a real grindy partial — only the one-tap/editor
   separates them), DL-1-2024 +1 (detect, <4 reps = below gate minimum), ROW-4-0608 −2
   (dead-front defeats every tool), SC-1 loss 65vs27 (single-DB accessory).

17. **LLM-tap experiment (2026-06-11, lifter-audited): the tap (with re-tap + fallback) edges
   auto on counts (0.23/0.16 vs 0.31/0.24, 26-clip corpus) but LOSES on velocity-loss (7.7 vs
   6.0pp) — auto's flow-verification picks better-quality TRACKS than a human seed.** BN-4-0609:
   tap counted 10/10 but read loss 7% vs Vitruve 45% (auto's candidate: 1.4pp) — count-equal ≠
   velocity-equal. Product rule: the user's tap enters as a PRIORITY CANDIDATE through the same
   verification scoring, never a blind override. **⚑ The BODY-LOCK trap (lifter-caught): a tap
   on the LIFTER (RDL hip) tracks the hinge at perfect rep cadence — passes the static guard,
   would pass verification scoring, produces plausible counts with meaningless velocity. Only
   the human reviewing the tracked overlay catches it** → the tap-confirm UI must play back WHAT
   is tracked; cheap guard to build: `no_plate_at_lock` (no plate-circle detectable at the locked
   target). Other audit findings: ROW-2-0608's tap was wrong at frame 0 and recovered by luck;
   SC-1's −1 and bad loss are late-set DRIFT off the DB, not segmentation. Static guard caught 5
   floor/background mis-taps live; matte plates need the tap on the textured HUB/logo (flow needs
   corners); ROW-4 untappable (#12). Corpus now 26 clips (06-10 Equinox registered); valid tap
   seeds in `cv_eval.py` CLIPS (RDL taps removed — body-tracks), reproduce with `--gate`.

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

## IMU Signal Processing Guidance

When working with Apple Watch IMU data for velocity measurement (see `REFERENCES.md` for citations):

1. **Use `CMDeviceMotion`, not raw `CMAccelerometerData`.** Device motion provides gravity-corrected acceleration in the device's reference frame and an orientation quaternion (`CMAttitude`). Integrating raw accelerometer data without gravity subtraction and orientation correction produces drift that no downstream filter can fix.
2. **Rotate acceleration into world frame before integration.** Use the `CMAttitude` quaternion to transform device-frame acceleration into a fixed world frame, then isolate the vertical (Z, gravity-aligned) component. Only after this rotation is integration to velocity meaningful.
3. **Apply Zero Velocity Update (ZVU) between reps.** Naive integration of acceleration drifts unboundedly. Detect rep boundaries (top/bottom of lift = momentary zero velocity) and reset integrated velocity to zero at those points. Standard in both the Achermann methodology and the Wojtek120 open-source reference.
4. **Sample at 100 Hz.** Matches the Achermann validation methodology; higher rates aren't necessarily better — match the reference for comparability.
5. **Calibrate per-device.** MEMS IMUs have per-unit offsets and scale factors. Capture stationary readings to estimate accelerometer bias before each session (or at first-launch).
6. **Validate against ground truth.** Target: r > 0.95, SEE < 0.07 m/s for mean concentric velocity vs an LPT or video reference. Worse than this means a pipeline bug, not a hardware limit — Achermann hit r > 0.97.
