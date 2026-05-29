# VBT reference & competitive landscape

> **Sourcing caveat.** Compiled May 2026 primarily from web-search snippets
> (this environment blocked full-text fetch of metric.coach *and* PMC/NSCA/
> journals). Treat numbers as field-consensus / vendor-stated, **not
> independently verified** — re-pull the primaries (links below) before relying
> on exact figures. Where a claim is single-snippet it's marked *(unverified)*.

## 1. Accuracy benchmarks & calibration targets

| Tool | Modality | Reported accuracy (vs criterion) |
|---|---|---|
| GymAware (gold standard LPT) | tethered linear transducer | r ≈ 0.90–1.0, SEE 0.01–0.08 m/s |
| Metric (Taber 2023, beta v0.5.4) | phone CV | velocity r 0.67–0.95, ICC 0.79–0.94, bias <0.06 m/s; ROM bias <2 cm |
| Metric (Deakin/PeerJ 2024, later build) | phone CV | velocity agreement **poor-to-moderate**; **proportional bias ↑ with velocity**; failed ICC≥0.997/CV≤3.5%; rep detection >95% |

**Key lesson for our calibration:** video velocity error is **velocity-dependent**
(proportional bias), not a constant offset. The watch↔Vitruve and any video↔truth
correction must be modeled across the velocity range, not as a single scalar.
This is almost certainly why Metric/SmartBarbell/Stance diverged most on the fast
early reps of the test set.

Primaries to re-pull: Taber et al. 2023, *Int J Strength Cond* 3(1),
DOI 10.47206/ijsc.v3i1.263 (open PDF on journal.iusca.org) · Deakin 2024,
PeerJ 17789 / PMC11283170.

## 2. Competitive landscape (tools currently in personal testing)

| Tool | Modality | Output | Export | Strengths | Failure modes |
|---|---|---|---|---|---|
| **Vitruve** (arriving) | on-bar device | per-rep mean/peak, ROM, +TtP/accel-index | **CSV/Excel** (Teams); enterprise API | calibration ground truth | barbell-only; strap |
| **Stance** | on-bar device | per-rep mean/peak; "Readiness" | none found (extract) | drift-free, caught all 8 reps | barbell-only |
| **Metric** | phone CV (plate) | rep table + velocity trace + bar-path; 60+ exercises | video only (no CSV found) | best video pipeline; matched on-bar shape | lighting/glare/contrast; non-circular plates; velocity proportional bias |
| **SmartBarbell** | phone CV (region) | tidy rep table + bar path | in-app share | robust to angle (region track) | dropped the grindy last rep; reads low mid-set; phantom 0.00 rows |
| **WL Analysis** | phone CV (plate) | **per-frame** velocity/accel/disp/power/force | **txt** (per-frame or averages) | richest raw signal (≈ our pipeline) | no rep table; "lbs" label is actually kg |

Cross-app on one real 330×8 deadlift: **set-average converged (~0.38–0.45 m/s),
per-rep diverged, the terminal rep diverged most** (Stance 0.20 / Metric 0.32 /
SmartBarbell missed). Evidence that every source is fallible and the
fatigue-critical last reps are where measurement is least reliable → the case for
confidence-weighted fusion + a rep-shape prior.

## 3. Metric definitions (the derivable feature set from one trace + load)

- **Mean concentric velocity** (m/s) — avg bar speed over the concentric phase. Most reliable; primary metric.
- **Peak velocity** (m/s) — max instantaneous speed in a rep. Noisier; for explosive lifts.
- **Time-to-peak velocity** (s) — how fast you accelerate to peak; an **RFD proxy**. Time-domain → robust on grindy reps (see fusion doc).
- **Mean/peak power** (W) — load × velocity × g; mean = avg over concentric samples.
- **Eccentric power** (W) — power absorbed controlling the descent. **Artifact-prone / noisy.**
- **Concentric / eccentric tempo** (s) — phase durations; feed TUT.
- **ROM** (cm) — bar displacement low→high per rep. Measured *directly* by video/BLE (no drift).
- **Time under tension** (s) — total rep duration (concentric+eccentric+pause).
- **Shift / bar-path deviation** — trajectory deviation (e.g. forward drift); technique flag.

## 4. Load–velocity profile (LVP) & 1RM

Linear fit of best-rep velocity vs load (exercise- & lifter-specific). Extrapolate
to the **MVT** intercept → predicted 1RM. 2-point method (≈45% & ≈85%) is a
validated shortcut; light loads carry more error. Rule of thumb: ~+0.05 m/s at a
fixed load ≈ ~+2.5% 1RM *(unverified)*.

## 5. Velocity zones (Mann, mean velocity — approximate)

| Zone | m/s | Goal |
|---|---|---|
| Absolute strength | 0–0.50 | near-1RM |
| Accelerative strength | 0.50–0.75 | strength/hypertrophy |
| Strength-speed | 0.75–1.0 | |
| Speed-strength | 1.0–1.3 | |
| Speed/starting strength | >1.3 | |

Hypertrophy commonly cited ~0.4–0.75 m/s.

## 6. Velocity loss (proximity-to-failure / fatigue proxy)

- Definition: % drop from fastest to last rep in a set.
- Auto-cut thresholds: **~10%** (power, fresh), **~20%** (strength), **~30%+** (hypertrophy/volume).
- Pareja-Blanco 2017 (VL20 vs VL40, back squat): similar strength gains; **VL20 → larger jump (CMJ) gains with ~40% fewer reps**; VL40 → more hypertrophy + shift to slower fiber phenotype. *(snippet; verify PMID 27038416)*
- Possible sex difference: women may need higher VL (~40%) for strength/power. *(unverified)*

## 7. Minimum velocity thresholds (mean velocity at failure/1RM)

- Bench ≈ 0.15–0.17 m/s · Back squat ≈ 0.30 m/s · **Deadlift ≈ 0.25 m/s**.
- Lift- and lifter-specific (don't reuse across lifts). The LVP y-intercept for 1RM estimation.

## 8. Product/UX ideas worth stealing

- **Readiness from first-3-reps vs 6-week baseline** — zero-input daily autoregulation.
- **Retroactive metric backfilling** — ship a new metric, recompute it across all history so users get instant value.
- **Per-exercise metric customization** (different highlights for squat vs bench).
- **Video-as-artifact** — the recording is both the measurement input and the shareable coaching deliverable (bar-path overlay export).
- **Mid-set adjustable real-time audio feedback**; **Apple Watch as a remote** to start/stop recording.
- **🅥 marker** distinguishing velocity-trackable vs manual-entry exercises in a mixed library.

## 9. Implications for our app

1. **Calibration must be velocity-dependent** (proportional bias), not a single offset — fit the correction across the velocity range, anchored on Vitruve/Stance.
2. **Per-rep confidence + per-metric reliability is an open differentiator** — no competitor clearly surfaces it.
3. **Lean on time-domain fatigue metrics** (time-to-peak, tempo) for robustness on the grindy terminal reps where magnitude metrics get noisy.
4. **MVT ≈ 0.25 m/s (deadlift)** is a useful built-in failure anchor for both imputation plausibility and 1RM estimation.
5. Video competitors are **plate-dependent and lighting-sensitive**; a tracker that degrades gracefully (region/joint tracking, any-lift) is a real wedge.
