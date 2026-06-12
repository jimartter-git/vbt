# VBT reference & competitive landscape

> **Sourcing.** Compiled May 2026. Sections 1–9 were first drafted from
> web-search snippets, then **corrected against full-text PDFs** the user
> supplied (21 papers/articles). Caveats remain: several "validation" PDFs are
> Metric's own *blog summaries* of studies (vendor-authored), not the peer-
> reviewed papers; only Renner 2025 (PLOS ONE) and Šagovac 2024 (thesis) are
> independent primary sources here. Items still unconfirmed are marked
> *(unverified)*.

## 1. Accuracy benchmarks & calibration targets

Independent / vendor validations of **Metric** (phone CV), newest-relevant first:

| Study (source type) | Setup | Velocity result | Notes |
|---|---|---|---|
| **Renner, Mitter & Baca 2025** — PLOS ONE *(independent)* | Qwik/Metric/MyLift vs Vicon + RepOne LPT; n=20 powerlifters, 589 reps, squat/bench/DL 45–90% | Metric bias: bench +0.07, DL +0.14, squat −0.28 m/s; RMSE 0.04–0.08 | **Metric missed ~17% of deadlift reps** + 16 ghost reps; Qwik best, 0 missed |
| **Trowell 2024** *(vendor summary; PeerJ/Deakin unconfirmed)* | Metric v0.6.0 vs Vicon; n=24, squat+bench only, 5 angles 0/±10/±20° | Lin's CCC 0.83–0.93; **consistent +0.06–0.13 m/s overestimation**, worst at ±20° | rep detect >99% squat, 94–97% bench; "not a valid velocity tool at v0.6" |
| **Šagovac 2024** — MSc thesis *(independent-ish)* | Metric v4.5.0 vs **Vitruve LPT**; n=15, bench, 45/60/75% | r=0.93 mean vel; ICC 0.89–0.97; bias +0.01±0.06 | 100% rep detection |
| **Taber et al. 2023** — IJSC *(vendor summary)* | Metric v0.5.4 vs 3D mocap; ~800 reps, bench/squat/DL | r 0.67–0.95; ICC 0.79–0.98; bias 0.01–0.02 (fast squat +0.06) | ROM bias <2 cm |
| **Metric internal** *(marketing)* | v0.3 vs OptiTrack; **n=1**, 48 reps | r=0.984 | single-subject; ignore for accuracy |

**Calibration design (corrected):** the evidence points to a **roughly constant
systematic offset** (over- or under-estimation depending on build), *not* a
velocity-proportional error — and in our own cross-app test Metric tracked
Stance at ~+0.045 m/s nearly constantly. So **start with a simple offset / linear
fit** for watch↔Vitruve correction; keep a velocity term *available* and confirm
with a Bland-Altman regression slope before assuming it's needed. Error that *does*
grow is with **camera angle** (video) — not our concern for the watch, but a
reason video sources need a setup-quality confidence signal.

Gold-standard comparator: GymAware (tethered LPT) r ≈ 0.90–1.0, SEE 0.01–0.08 m/s.
Lesson from Renner: **video VBT systematically struggles with deadlift rep
detection** (~17% missed) — exactly the dropped-rep failure we saw in SmartBarbell.

## 2. Competitive landscape (tools currently in personal testing)

| Tool | Modality | Output | Export | Strengths | Failure modes |
|---|---|---|---|---|---|
| **Vitruve** (arriving) | on-bar device | per-rep mean/peak, ROM | **CSV/Excel** (Teams); enterprise API | calibration ground truth | barbell-only; strap |
| **Stance** | on-bar device | per-rep mean/peak; "Readiness" | none found (extract) | drift-free; caught all 8 reps | barbell-only |
| **Metric** | phone CV (plate) | rep table + velocity trace + bar-path; 60+ exercises; reads ~high | video only (no CSV) | best video pipeline; ~constant offset vs device | lighting/glare/angle; non-circular plates; ~17% DL reps missed (Renner) |
| **SmartBarbell** | phone CV (region) | tidy rep table + bar path | in-app share | robust to angle | dropped grindy last rep; phantom 0.00 rows |
| **WL Analysis** | phone CV (plate) | **per-frame** velocity/accel/disp/power/force | **txt** (per-frame or avg) | richest raw signal (≈ our pipeline) | no rep table; "lbs" is actually kg |

On one real 330×8 deadlift: **set-average converged (~0.38–0.45 m/s), per-rep
diverged, terminal rep diverged most** (Stance 0.20 / Metric 0.32 / SmartBarbell
missed). Every source is fallible and the fatigue-critical last reps are where
measurement is least reliable → confidence-weighted fusion + a rep-shape prior.

## 2b. Stance build 1.9.15 intel *(lifter-supplied WhatsApp/TestFlight captures, 2026-06-12)*

Stance (on-bar sensor) is shipping **sensor + video fusion with a human-in-the-loop tap**
— massive convergent validation of this project's architecture, from the device company:

- **Tap UX**: "Tap the inside of the plate (where the bar enters the plate) in the first
  frame… Pinch to zoom for a more precise tap" — the HUB tap + zoom, independently
  converging on our learning #18. Their dev overlay shows a point cloud ("pts=17") seeded
  at a hub marker + a height(t) chart with phase-shaded segmentation ≈ our FlowTracker
  architecture almost exactly.
- **Per-rep fusion, human-arbitrated**: "Matched rep — Current (ML) mean 0.41/peak 0.77 →
  Video mean 0.40/peak 0.71 — [Replace rep]" — sensor and video matched rep-by-rep,
  disagreement SURFACED, user replaces per rep. A manual version of our per-primitive
  fusion design (and our guardrail #3, in production).
- **Their stated motivation = our thesis**: "the current algorithm struggles most on slow
  reps — an accelerometer can't detect…" (IMU weak exactly where video is strong; they're
  fusing for the grindy terminal reps).
- **Capture guidance** (annotated photo): plate in full view through the rep; film ~45°;
  don't walk in front; **no touch-and-go / stiff-leg deadlifts** (their segmentation
  limit — same family as Vitruve's TnG row failure); sensor strap position; "zero rep
  issue" acknowledged (their static-seed analog). Edit window: 2 h post-set.

**Where we're already ahead of this build**: their tap is FIRST-FRAME-ONLY (the
constraint we proved fatal on RDL/dark-iron clips and removed with tap-on-any-frame +
bidirectional tracking, learning #18); their fusion is fully manual per-rep replacement
vs our designed confidence-weighted auto-fusion with flag-on-disagreement; and they
explicitly exclude touch-and-go, which our relative gate handles (SQ-3 exact). Where
they're ahead: it's SHIPPED, sensor-grade absolute velocity comes free from the device,
and video is positioned as the *correction* channel — pragmatic sequencing worth noting.

## 3. Metric definitions (the derivable feature set from one trace + load)

- **Mean (concentric) velocity** (m/s) — avg bar speed over concentric. Primary; most reliable (r²≈0.94 with peak).
- **Peak velocity** (m/s) — max instantaneous; explicitly **noisy** (vibration/jerk spikes).
- **Time-to-peak velocity** (s) — `peak_velocity_timestamp − concentric_start`; an **RFD proxy** and *"one of the first metrics to deteriorate under fatigue."*
- **Mean/peak power** (W) — force × velocity; peak power peaks ~30–60% 1RM.
- **Eccentric power** (W) — energy absorbed over the *active braking phase only* (peak eccentric velocity → stop). Metric's purpose-built fix for the artifact-proneness of eccentric *velocity*; can still throw outliers in practice.
- **Concentric / eccentric tempo, top/bottom pause, time under tension** (s).
- **ROM** (cm) — concentric displacement; measured *directly* by video/BLE (no drift).
- **Shift / bar-path deviation** — trajectory deviation; technique flag.

## 4. Load–velocity profile (LVP) & 1RM

Linear fit of **best-rep velocity** vs load over ≥3 sets (warm-ups count), extended
to the **MVT** intercept → estimated 1RM. Accuracy cited via Jidovtseff 2011
(bench <5%) and Banyard 2018 (squat <3% error). Marginal rule appears in two forms
in Metric's own copy — "+0.05 m/s ≈ +2.5% 1RM" *and* "≈ 5% 1RM" — i.e. **internally
inconsistent vendor claim; don't rely on it.**

Expected mean velocity by %1RM (Metric): ~100% → 0.2–0.4; ~80% → 0.4–0.7; ~60% → 0.8–1.2 m/s.

## 5. Velocity zones — contested

The Mann 5-zone bands (strength 0–0.5, accel-strength 0.5–0.75, strength-speed
0.75–1.0, speed-strength 1.0–1.3, speed >1.3 m/s) are widely cited **but Metric
explicitly rejects fixed zones** ("the five velocity zones ain't it") in favor of
each lifter's **rolling personal baseline** (e.g. vs a 6-week average). Our design
should treat absolute zones as weak priors and lean on personalized baselines.

## 6. Velocity loss (proximity-to-failure / fatigue proxy)

- % drop from fastest to last rep in a set.
- Metric's emphasis: **~20–25% VL ≈ RPE 8** for strength; ~10–15% ≈ RPE 6–7; **~40% ≈ failure / RPE 10**. (The generic "10/20/30% per goal" framing is field-common but Metric centers on 20–25%.)
- Pareja-Blanco 2017 (VL20 favored for jump gains with fewer reps) was *not* in the supplied PDFs — *(unverified; pull PMID 27038416)*.

## 7. Minimum velocity thresholds (mean velocity at 1RM/failure)

Metric's own stated table (mean velocity; Novice / Intermediate / Advanced):

| Lift | Nov | Int | Adv |
|---|---|---|---|
| Back squat | 0.40 | 0.30 | 0.25 |
| Bench | 0.30 | 0.20 | 0.12 |
| **Deadlift** | 0.35 | **0.20** | **0.15** |
| Sumo DL | 0.30 | 0.20 | 0.10 |
| OHP | 0.35 | 0.25 | 0.15 |
| Front squat | 0.40 | 0.35 | 0.30 |

**Correction:** earlier we held "deadlift MVT ≈ 0.25" — that's actually *back-squat*
advanced. Deadlift MVT is ~**0.15–0.20**. Lift- & lifter-specific; set once and
keep it.

## 7b. OVR Performance conversion charts *(vendor ad graphics, 2026-06-12 — UNVERIFIED weak priors)*

OVR Performance (bar-mounted VBT device, Vitruve-style) publishes two conversion tables
(lifter-supplied screenshots; OVR's own fine print: "estimates — each athlete will have a
unique load-velocity profile"):

**%1RM → mean velocity (m/s):**

| %1RM | Squat | Bench | Deadlift |
|---|---|---|---|
| 40% | 1.20 | 1.05 | – |
| 50% | 1.05 | 0.90 | – |
| 60% | 0.90 | 0.75 | 0.60 |
| 70% | 0.75 | 0.60 | 0.50 |
| 80% | 0.60 | 0.45 | 0.45 |
| 90% | 0.45 | 0.30 | 0.30 |
| 100% | **0.30** | **0.18** | **0.18** |

**RPE ↔ RIR ↔ velocity-loss ↔ last-rep velocity:** RPE 5.5→10 ↔ RIR 4→0 ↔
VL 5→45% ↔ last-rep 0.55→0.25 m/s (generic, lift-unspecified frame).

**Why filed (cross-vendor convergence — strengthens, doesn't replace, §6/§7):**
- OVR's 100%-1RM row sits inside Metric's MVT bands and independently re-confirms
  **deadlift MVT ≈ 0.18, not 0.25** (learning #6). Two vendors, same answer.
- OVR RPE 8 ↔ ~20–25% VL = exactly Metric's strength anchor (§6); RPE 10 ↔ 40–45% ≈
  "failure ~40%". The VL→RPE mapping is now double-sourced.
- vs the PERSONAL curves (`dataset/priors/`): the lifter's grind velocities sit BELOW
  OVR's generic floors on all three lifts (SQ 0.22 vs 0.30, BN 0.10 vs 0.18, DL 0.12 vs
  0.18) — an "advanced" profile, and a concrete demonstration of why personal priors
  must override universal ones (§5). Use OVR/Metric tables as cold-start bounds only.

## 8. Product/UX ideas worth stealing

- **Readiness from first-3-reps vs 6-week baseline** — zero-input autoregulation.
- **Retroactive metric backfilling** — ship a metric, recompute it across all history.
- **Configurable real-time audio feedback** (announce / target-zone chime / VL-threshold warning, 5–45%), adjustable mid-set.
- **Dual-pass CV**: light real-time pass + accurate post-set re-analysis (un-rack events filtered post-set).
- **Per-exercise metric defaults** (eccentric tempo on RDLs, peak power on cleans).
- **Video-as-artifact** — recording is both sensor input and shareable coaching deliverable (bar-path overlay export).
- **🅥 marker** distinguishing velocity-trackable vs manual-entry exercises.

## 9. Implications for our app

1. **Calibration: start with a constant offset / linear fit** (verify Bland-Altman slope before adding a velocity term). Not the velocity-dependent model we first assumed.
2. **Per-rep confidence + per-metric reliability is open white space** — no competitor clearly surfaces measurement confidence.
3. **Lean on time-domain fatigue metrics** (time-to-peak, tempo) on grindy terminal reps where magnitude metrics get noisy.
4. **Deadlift rep detection is a known video weakness** (Renner: ~17% missed) — our fusion + rep-plausibility + (eventually) watch-as-second-source directly attack this.
5. **Personal rolling baselines > fixed velocity zones** (Metric's own stance); MVT ≈ 0.15–0.20 deadlift as a soft failure anchor.
6. Video competitors degrade with **angle/lighting/plate shape** — graceful degradation (region/joint tracking, any-lift) is a real wedge.
