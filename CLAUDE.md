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

- **PoC scaffold — now DEVICE-VALIDATED (2026-06-15, Apple Watch Ultra, watchOS
  26.5):** watchOS app (HKWorkoutSession + CMBatchedSensorManager → CSV → phone),
  iOS companion, shared `VBTCore` Swift package, Python ZUPT analysis pipeline
  (`analysis/`, tests green). **⚑ The riskiest assumption is answered YES:** the
  scaffold built/signed/ran on a real Ultra unmodified, `CMBatchedSensorManager`
  sustained **~200 Hz continuously (5,317 samples ≈ 27 s)** inside an
  `HKWorkoutSession`, and the CSV transferred watch→phone intact (`transferFile` →
  `VBTPhone` list). Validated on a SINGLE ~27 s set; multi-set thermal/battery
  endurance and signal *accuracy* vs Vitruve are still untested (next).
- **Active phase = data + calibration.** Building a personal multi-vendor
  measurement database (`dataset/`) to quantify cross-tool agreement, calibrate,
  and seed the app's per-user prior. **Vitruve is the established ground-truth
  reference** (since 2026-06-02; `compare.py` auto-prefers it — ~392 rep rows across
  bench/squat/skull-crushers, etc.).
- **⚑ Data ingested through 2026-06-16** (no known backlog): 06-05 BN/DL, 06-08 rows,
  06-09 bench, 06-10 squats/RDLs, 06-11 incline bench (Vitruve+SB), 06-13 deadlifts (6 sets,
  full Vitruve+SB GT, **all 6 CV counts EXACT**), 06-15 barbell rows (5 sets, Vitruve GT — set 1's
  first 2 reps dropped as leftover warmup; +5 Apple Watch IMU = the FIRST real watch data, analyzed
  vs Vitruve; +5 row videos CV-scored EXACT), **06-16 bench (5×10, RPE 7.5/6.5/7/8/9.5, Vitruve GT + 5 Apple Watch IMU
  `dataset/raw/20260616-BN-*_watch.csv` + 5 R2 videos `20260616-BN_*.mov`) — the FIRST all-four-inputs
  testbed. After the UN/RERACK fix (learning #25, `transit_aware` + confirmed deep-dish rim): CV tap
  path **reps 10/10 EXACT all 5**, **abs MV RMSE 0.040 ≈ SmartBarbell 0.039 (TIED)**, VL within ~4pp
  on 3/5 (SB also 10/10, RMSE 0.039). Watch bench DIAGNOSED (slow/paused/supine → detector over-
  segments; position-cycle reaches r 0.82-0.95 per-set but not yet robust; ROM good ~0.31). See
  learnings #24 (ingest) + #25 (the fix).** (06-10 filed as set-level Vitruve averages — the app
  crashed before per-rep export.) Next upload → follow the ingestion + video triggers below.
- **⚑ Video storage built (2026-06-15): HD masters live in Cloudflare R2** (bucket `vbt-video`),
  repo keeps only `dataset/raw/manifest.csv` pointer + `vbt_video/clip_store.py::resolve_clip()`
  (local→cache→download). **Don't commit HD video to git** — upload to R2, add a manifest row.
  New **CV-training corpus**: `dataset/clips.csv` (wide human annotations, `dataset/ANNOTATIONS.md`
  vocab) + `tools/ingest_clips.py` (probe + seed-free CV prefill; `--from-manifest` pulls from R2).
  Full design + next-session runbook: `docs/video-storage.md`. **⚑ 06-13 HD deadlifts CV-scored
  2026-06-15 — ALL SIX EXACT (reps_cv 5/3/2/2/8/8 = GT) after fixing TWO bugs: iPhone display
  ROTATION (#22) + the deadlift double-bump SEGMENTER (#21).** The over-count *looked* like
  "CV can't see dark iron"; it was two mechanical bugs. (a) DL-1..5 are iPhone `frame.rotation=-90`
  clips — `PyAVDecoder` decoded them sideways so the bar moved along image-X while the segmenter
  read Y (track looked static, count garbage); now `PyAVDecoder._apply_rotation` decodes upright.
  (b) the deadlift double-humped pull (knee/sticking-point dip) faked a turnaround → ~2× over-split;
  the double-bump merge fixes it. Counts: DL-1/2/3/4/6 zero-tap auto-seed, DL-5 one-tap on the
  yellow-hub plate (auto grabbed a floor decoy). **Velocity-LOSS — the fatigue signal — matches
  Vitruve: 17.8 vs 17.1, 29.0 vs 29.7, 11.9 vs 9.4 pp.** Absolute MV reads a consistent ~1.2× high
  (active-region vs full-concentric mean DEFINITION gap, correctable — not a tracking error). Native
  4K is impractical to flow over (hours/clip) so scoring uses an UPRIGHT 720p proxy
  (`tools/_dl0613_proxy_cv.py`, rotation-aware). Records in `clips.csv`/`manifest.csv`/`sets.csv`.
- **⚑ CV milestone (2026-06-12): ALL THREE product metrics now beat SmartBarbell.** Scoreboard:
  **`docs/cv-fusion.md` → "Full scoreboard snapshot (2026-06-12)"**. Human-grade tap path: reps
  **0.12** (wtd 0.07, 24/26 exact) vs SB 2.57 · velocity-loss **2.2pp** vs 9.0 · **absolute m/s
  0.055 vs 0.068 — the open metric, closed by the human-confirmed rim** (`rim_px`, #19–#20).
  Auto/no-tap: 0.31/0.24, loss 6.0pp. ONE canonical loss everywhere (`vbt_analysis/metrics.py`).
  Bilateral fusion built+validated, gated on both-plates-in-frame footage. ROM priors derived
  (`dataset/priors/*_rom.csv`). Key rules: learnings #16–#20.

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

18. **Tap-on-ANY-frame made the one-tap path HUMAN-GRADE (2026-06-11): reps 0.12/0.07 (24/26
   exact, every tappable clip exact), velocity-loss 2.4pp vs Vitruve — beats auto (0.31/0.24,
   6.0pp) and SB (2.57, 9.0pp) decisively, with every track VISUALLY verified riding the plate.**
   The frame-0 constraint was the real enemy, not tap judgment: `seed_time` + `track.
   ReplaySource`/`track_bidirectional` seed at the plate's clearest frame and track BOTH ways
   (drift halves; the RDL body-fusion and dark-iron at-rest texturelessness dissolve). CLIPS
   seeds may be `(x,y,w,h,t)`; reproduce with `--gate`; the loop is tooling:
   `analysis/scripts/tap_workbench.py` (motion heatmap → scrub → zoom → tap → tracked-overlay
   verify). Validated tap rules: seed at a SHARP PAUSE (mid-rep blur = bad corners); tight box
   on the textured HUB excluding background (background corners outvote a textureless plate —
   rim box static, hub box 10/10 on ROW-2-0608); mid-set seeds beat early ones; overlay
   verification is non-negotiable (every failure mode is visible there and nowhere else).
   Dark-iron any-frame taps read near device-grade ABSOLUTE m/s (BN-1-0609 0.43→0.24 vs Vitruve
   0.49→0.26). Honest floors that remain: RDL-1 7/8 (segmentation, dead-on track, auto agrees),
   ROW-4 dead-front (edge-on sliver, untrackable for every tool), BN-3-0605 loss 11.5pp
   (diagonal-bumper perspective scale varies through the ROM — physics). Product UX = scrub →
   tap → watch the box track → accept/re-tap.

19. **Absolute velocity WON via the human-confirmed RIM, not better auto-measurement (2026-06-12):
   tap 0.057 vs SB 0.068 set-MV |err| (common 11) — all three product metrics now beat SB.** The
   new abs-velocity harness (`vel_eval.py --tap`, also per-rep RMSE) localized ALL remaining
   error in 5 clips with ONE mechanism: the ruler measured the ~113px HUB, not the ~210px RIM
   (diagonal bumpers ~2×, hex squats ~1.25×). Fix = learning #10's confirm/adjust surface made
   real: `VideoConfig.rim_px` (+ `cv_eval.RIM_PX`), a per-clip human circle-confirm — scale-only,
   tracking untouched, loss unchanged (scale-invariant ✓). Any-frame taps alone were ALREADY
   device-grade on dark iron + deadlifts (rRMSE 0.01–0.10). Same session: **bilateral fusion
   built + validated** (`vbt_video/bilateral.py`: tilt cancellation; f-free depth tier
   pos=−D·(cy−cy0)/d(t); per-rep `lr_disagree` flags — a deliberately bad second end got 10/10
   reps flagged, guardrail #3 proven) but **productively GATED**: clips needing scale help have
   the far plate OFF-frame; capture ask = both plates in frame, side-on, Vitruve running. ROM
   priors now derived from Vitruve rows (`derive_rom_priors.py`, advisory `rom_prior_cm` —
   flags, never gates; a whole-set outlier = scale-error tell). Residuals, named: BN-2/3-0605
   0.14/0.11 (perspective-through-ROM → the depth tier fed by rim-anchored size traces), SC-1
   (accessory, not chased). Thin margin — honest: we edge SB on abs, not crush it.

20. **Continuous-ruler campaign (2026-06-12): built, synthetically exact, GATED OFF on real
   440px clips — the postmortem that names the per-clip absolute floor.** SB's remaining
   per-clip edge (0605 diagonal benches, SQ-3) = per-frame plate re-measurement. Our tier
   (`depth_scale`: pos=−D·(cy−cy0)/d(t), anchored AT the rim-confirm frame `rim_t` —
   median-anchoring re-scales the ruler, caught synthetically) is pinhole-exact in tests,
   but BOTH 440px trace sources fail honestly: Hough traces hub/rim MODE-SWITCH (40% fake
   swings, auto-abstained by a 25% physical range cap — it changed a rep count before the
   cap); colour-mask traces are clean signals whose SHAPE conflates mask-fraction (arm
   crossings; upper-envelope insufficient) with perspective — helps one bench, hurts
   another, no shared gate separates them → default OFF (robust_scale precedent). One more
   constant-rim win: BN-4 hex rim 110px (uniform −23% bias = oversized ruler, independently
   flagged by the ROM prior) → 0.05. DL-2's rim attempt REGRESSED and was reverted —
   front-quarter deadlift = real out-of-plane motion; no static rim fixes it. Final: abs
   **0.055 vs SB 0.068** aggregate, per-rep RMSE 0.081 wtd, loss/counts untouched. The
   named unlocks for per-clip parity: (a) **learned plate sizer (torch-gated — NOW the
   single bottleneck)**, (b) HD/closer capture, (c) both-plates footage → bilateral d(t)
   cross-check. Don't re-attempt classical per-frame sizing at 440px.

21. **The 06-13 deadlift "failure" was SEGMENTATION, not tracking — the double-bump merge
   (2026-06-15).** The dark round-iron 4K deadlifts AUTO-over-counted ~2× (DL-6 8-rep set read
   15-21), which *looked* like "CV can't see dark iron." It wasn't: flow rides the bar perfectly
   (DL-6: **311px travel ≈ a full plate, conf 1.0, 8 clean position cycles = GT**) — but
   `trajectory_to_reps` segments on velocity ZERO-CROSSINGS, and a deadlift's **double-humped pull
   (the knee/sticking-point velocity DIP)** fakes a turnaround, splitting each rep into 2-3. The
   corpus that "won" was bench/squat = single-humped. Fix: `kinematics._merge_subrep_runs` (in
   `_segment_concentric`) coalesces consecutive positive-velocity runs **not separated by a real
   bar RETURN toward the bottom** (bench→chest/squat→depth/deadlift→floor all reset fully; a
   sticking-point dip doesn't). Lift-agnostic; two guards keep it from eating real reps:
   (a) **`sep_frac=0.2`** sits in the *measured* gap between mid-rep dips (≤0.04×ROM) and real
   eccentrics (≥0.32×ROM — even SQ-1 low-res / SQ-3 fast-TnG); **0.4 over-merged SQ-1** (a main-lift
   regression, learning #15 — the line we don't cross). (b) an **overtop guard** (don't absorb a
   run rising >1.0×ROM ABOVE the rep top) stops a terminal rack-lift from fusing into the last real
   rep, which would then make the plausibility gate drop it (caught by
   `test_plausibility_gate_drops_rack_phantoms`); ROM here is the **median of real eccentric
   descents** (phantom-robust, not the raw range a rack-lift inflates). **Validated: a full
   merge-ON-vs-OFF diff over the whole corpus = 0 regressions (only ROW-2-0608 *improved* 7→6);
   all 50 tests pass.** This was ONE of two bugs behind the 06-13 over-count; the other was
   rotation (#22). Method: when an AUTO count is ~2× and the bar visibly tracks, suspect the
   SEGMENTER, not the tracker — dump the trajectory and count position cycles before concluding
   "CV can't."

22. **The OTHER 06-13 bug: iPhone display ROTATION, ignored at the decode seam → ALL 6 deadlifts
   now EXACT (2026-06-15).** After the double-bump fix, DL-1..5 still mis-counted while DL-6 was
   perfect. Root cause: **DL-1..5 are iPhone clips with `frame.rotation = -90`** (landscape sensor
   + a portrait display matrix); DL-6 has rotation 0. `PyAVDecoder` decoded the RAW (sideways)
   frames, so the bar travelled along the image **X-axis** while `trajectory_to_reps` reads **Y** —
   the track looked STATIC (yspan 17px) and the count was garbage. This *masqueraded* as the
   dark-iron "wrong-seed" / detect-fallback problem (it is NOT — that diagnosis in #21 was wrong
   for these clips). Fix: `PyAVDecoder._apply_rotation` honours `frame.rotation` (`np.rot90`,
   k=r//90; verified -90→k=3=clockwise=upright) so EVERY downstream consumer gets upright frames —
   a real product bug (any portrait phone clip would have failed). Result with rotation+double-bump
   both fixed: **reps_cv 5/3/2/2/8/8 = GT, ALL SIX EXACT** (DL-1/2/3/4/6 zero-tap auto-seed; DL-5
   one-tap on the yellow-hub plate, auto grabbed a floor decoy). **Velocity-LOSS — the fatigue
   signal — matches Vitruve: DL-1 17.8 vs 17.1, DL-5 29.0 vs 29.7, DL-6 11.9 vs 9.4 pp.** Absolute
   MV reads a *consistent* ~1.2× high — a velocity-DEFINITION gap (our active-region mean vs
   Vitruve's full-concentric mean), correctable, NOT a tracking error. To SEE rotation: read
   `frame.rotation` (or render a frame and look) before trusting any "static track" on phone video.
   Tooling: `dataset/tools/_dl0613_proxy_cv.py` transcode now rotates upright too.

23. **FIRST real Apple Watch IMU vs Vitruve (2026-06-16, 06-15 barbell rows, 5 sets) — velocity
   is REAL, the rep DETECTOR is the gap, and the watch FILES were reverse-labeled.** The 200 Hz
   CMDeviceMotion CSVs (`ua_*`/`g_*`/`q_*`) drop straight into `vbt_analysis`. **Velocity signal
   holds:** ROM lands ~0.5 m zero-calibration, per-rep MV bias ~**−0.05 m/s** (the expected constant
   offset, learning #4) RMSE ~0.07–0.10 vs Vitruve. **Rep detection was the weak point:** the PoC
   `detect_turnarounds` over-counted (setup pull + pause-split zero-ROM + put-down) and under-counted
   slow sets. Two fixes: (a) **`velocity.gate_reps`** drops the junk by ROM/MV vs the robust median
   (15/11/12/12/6 → 10/10/10/9/6); (b) **`detect_turnarounds(decouple=True)`** — COUNT at a high
   cutoff, but SNAP anchors to the true turnaround (nearest minimum of a *gently* drift-removed
   velocity) so the high cutoff doesn't phase-shift anchors inward and inflate MV (a naive 0.25 Hz
   pushed synthetic 0.51→0.575; decoupled stays 0.52). **decouple is OFF by default** — on this data
   it's a wash (fixes ROW-4 9→10 but over-counts the clean ROW-3 10→11), reserved for genuinely
   drift-merged signals. **The "ROW-5 anomaly" was a FILE-LABEL REVERSAL, not a watch fault — caught
   by a velocity time-aligner (2026-06-16).** Symptom: watch "ROW-5" didn't match its video (10 clean
   even reps per video+Vitruve) — envelope xcorr 0.36, windows non-overlapping. I was WRONG FOUR times
   forcing a watch-fault story ("degraded capture" → "wrist decoupled/fatigue" → "CMDeviceMotion
   glitch") — each killed by going to the tape. The real cause: the watch files are **reverse-labeled,
   `watch_N = set (6−N)`**, proven by an all-pairs velocity cross-correlation matrix (`_align_matrix.py`):
   watch1↔video5 (r .90), watch2↔video4 (.90), watch3↔video3 (.97), watch4↔video2 (.92), all at a
   consistent ~+2 s lag; and the corrected mapping TIGHTENS the watch-vs-Vitruve aggregate (RMSE
   0.091→**0.069**, bias **−0.048** — at the project SEE<0.07 target). The file in the `_watch-5` slot
   is FOREIGN (device uptime 6549 vs ~15500 for the others = a different session; only r=0.46 to
   video1) → **set-1's watch recording is missing** (lifter-confirmed: a VBT-app mix-up deleting dummy
   extracts; only sets 2-5 captured). **FIXED: watch files RENAMED to true sets** (ROW-2/3/4/5_watch =
   sets 2/3/4/5; no ROW-1; dummy removed) — the harnesses that assume `watch_N=set_N` are now correct.
   The clincher was reading the clocks: watch `t` is device UPTIME (decreasing across the files =
   reverse order); videos carry **UTC `creation_time`** (increasing). **Lessons: (1) the BAR (video/Vitruve) is ground truth — when the watch
   disagrees, suspect the FILE then the watch, never the lifter; (2) before theorizing a sensor fault,
   CROSS-CORRELATE the signals AND check the clocks (uptime vs UTC); (3) velocity cross-corr IS the
   fusion time-sync — build it early.** Corrected watch×set map + per-set numbers live in the ROW
   `sets.csv` notes. Harnesses: `_watch_0615row.py`, `_watch_plot.py`, `_row5_overlay.py`, `_align_matrix.py`.

24. **06-16 bench (5×10; +Vitruve GT, +5 Apple Watch IMU, +5 R2 videos) — CV COUNTS the dark-iron
   bench but its VELOCITY doesn't hold on a diagonal end-ish view; bench watch IMU is below the row
   bar; and a "rotation" scare was a NON-bug (2026-06-16).** Three parts, all ingested:
   (a) **Vitruve**: 5 sets (set 1 = 225 lb top set, sets 2-5 = 205 lb back-offs). Lifter RPEs
   7.5/6.5/7/8/9.5 (set 5 hardest). NB: set 1's velocity-LOSS 42.5% at RPE 7.5 OVERSTATES
   proximity-to-failure — a clean learning-#6 data point (VL alone needs personal-MVT context).
   `_ingest_0616bn_vitruve.py`. (b) **CV (R2 videos)**: the AUTO zero-tap path is
   EXACT on BN-1/2/3 (10/10/10, conf 1.0, dark Rogue iron + blue hub, no tap) and reads 11 on
   BN-4/5 — a real put-down/rack cycle BOTH auto and one-tap see (auto mean|err| 0.4 < one-tap 0.6;
   one-tap's late auto-located hub seeds kept the put-down phantom the gate drops). **But velocity
   is UNRELIABLE here**: velocity-LOSS pins ~61-72% regardless of the true Vitruve loss
   (42/24/30/40/59%) — VL is scale-invariant, so this is a flow velocity PROFILE-shape problem on
   dark iron at this angle, not just scale (abs m/s was also hub-vs-rim inflated ~3× from the small
   hub seed). **COUNT is the deliverable; the capture ask for bench velocity is a clean SIDE-ON
   view.** ⚑ **SmartBarbell WINS this bench day** (`_ingest_0616bn_sb.py`, Westwood Athletics
   Richmond, Rogue DEEP-DISH plates — set 1 = 2×45, sets 2-5 = a 10+25 in front of one deep-dish
   45): SB counts **10/10 EXACT on all 5** (beats our 0.4 mean|err|) AND its velocity tracks Vitruve
   tightly (**bias +0.027, RMSE 0.040 m/s**, VL within a few pp on sets 1/4/5). The clean, well-lit,
   head-on clip is exactly SB's strong case; our flow over-counted the put-down (BN-4/5) and read a
   noisy velocity on the dark deep-dish iron. An honest loss — the kind to chase: a side-on capture +
   a learned plate sizer are the named unlocks. (c) **THE ROTATION NON-BUG**: these iPhone clips carry `frame.rotation=-90`, which
   `PyAVDecoder` ALREADY honours → upright 1080×1920, bar vertical. I nearly "fixed" a non-problem:
   a probe misread the DISPLAYMATRIX side-data as 0 and a RAW-decode optical-flow test (without
   applying rotation) showed the bar on image-X → looked like learning #22. **Lesson: to test the
   axis, run frames THROUGH `PyAVDecoder` (which rotates), never a raw `to_ndarray()`; and read
   `frame.rotation`, not the side-data probe.** A started `force_rotation` override was reverted
   (unneeded). (d) **Bench watch IMU** (`_watch_0616bn.py`): files correctly ordered this time (no
   reversal — uptime increases BN-1→5), ROM tracks the bar well (~0.31 vs Vitruve 0.33 m), but bench
   is SLOW/PAUSED/SUPINE so the PoC `detect_turnarounds` over-segments on the chest/lockout pauses
   and per-rep velocity resolution is weak: bench-gated aggregate **RMSE 0.091 m/s, r 0.59** (below
   the rows' 0.069 and the SEE<0.07 target), fatigue-decline shape muted. `gate_reps`'s row-tuned
   absolute thresholds (mv>0.45) don't fit bench (MV 0.19-0.42) — gated inline. A detector gap, not
   a sensor limit. Records: `clips.csv` (5), `sets.csv`/`manifest.csv` notes, `_record_0616bn_cv.py`.

25. **The UN/RERACK fix — 06-16 bench CV reps EXACT + velocity tied with SmartBarbell (2026-06-16).**
   The 06-16 bench (the FIRST all-four-inputs testbed: watch+CV+Vitruve+SB on every set) first
   FAILED CV: AUTO over-counted BN-4/5 (11) and velocity was meaningless (VL pinned ~61% vs true
   24-59%, abs m/s ~3× high). Two root causes, both found by dumping the trajectory (not theorizing):
   (a) **scale read the ~72px blue HUB, not the ~570px deep-dish RIM** (7× error) → ROM 218cm, and
   the tiny UNRACK bobble passed `rom_min` *because* the inflated scale made it look like 31cm (a
   scale bug causing a count bug). Fixed with the human-confirmed rim (`RIM_PX`, learning #19).
   (b) **segmentation was vertical-only; the un/rerack is HORIZONTAL** (lift off / yank back to the
   hooks). It leaked in as a leading +1 and, when the merge fused the rerack into the last rep,
   tanked that rep's velocity (BN-3 rep10: vy≫vx in the real rep, then vx hit −392px/s in the
   rerack). Fix (`VideoConfig.transit_aware`, kinematics.py): a horizontal-aware merge guard (never
   fuse a |Δx|>|Δy| run) + `_transit_gate` (leading/trailing: drop tiny-ROM unrack <0.3×median or a
   horizontal-dominated rerack). **Row-safe** (rows are vertical-dominated; mid-set reps untouched;
   partials ≥0.4× kept). **DEFAULT OFF** — the jittery seed-free AUTO track cascades (BN-3 auto
   10→5), so it's enabled ONLY on the seeded/tap path (`cv_eval --gate`, `vel_eval --tap`); every
   auto/validated path is byte-identical (53 tests pass, auto BN-3 still 10, deadlift double-bump
   untouched). **Result (tap path): 06-16 bench reps 10/10 EXACT all 5; abs MV RMSE mean 0.040 ≈ SB
   0.039 (TIED, was meaningless; beats SB on 3/5); VL within ~4pp on 3/5.** ⚑ **Watch on the same
   sets: DIAGNOSED, not closed.** Bench is slow/paused/supine → low single-integration SNR; the PoC
   velocity-crossing detector over-segments the pauses (r 0.59). A **position-cycle** detector that
   exploits the pauses (chest minima / lockout maxima) reaches per-rep **r 0.82-0.95** where it
   segments cleanly (BN-3 r=0.95) — the lever is SEGMENTATION, not the hardware (Achermann r>0.97) —
   but no single auto prominence robustly hits exact-10 AND high-r across all 5 (not production-ready;
   `_watch_0616bn_poscycle.py`). Next unlocks: Madgwick orientation fusion, a learned rep detector,
   the Achermann 100Hz protocol. Watch is already at target on FASTER lifts (rows RMSE 0.069). Method:
   when a velocity is "meaningless," DUMP THE TRAJECTORY (x AND y) before blaming the sensor — both
   bugs here were visible there and nowhere else. Snapshot: `docs/cv-fusion.md` 2026-06-16.

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
