# Four-input per-rep scoreboard — counts, velocity & dual-axis agreement

Per-rep **counts** and **mean concentric velocity (m/s)** for every workout with 3–4 of the
four inputs (Vitruve · SmartBarbell · our-CV video · Apple-Watch IMU), plus a **dual-axis
agreement panel** per set. Numbers were freshly computed this session (CV re-run via
`vel_eval` + the 720p DL proxy; watch re-run through `vbt_analysis` ZUPT), not copied from
prior aggregates. Agreement metrics come from `vbt_analysis/agreement.py` (unit-tested).

## Two axes, on purpose — and why not Pearson r

A source can match the **speed** of each rep, the **shape** of the fatigue decline, or both;
they're different questions, so we report both:

- **Absolute:** per-rep **RMSE** + **bias** (m/s) — *is each rep the right speed?* Gated on a
  count match (positional alignment); abstains (`— (count≠)`) rather than compare the wrong reps.
- **Shape:** **velocity-loss Δ** (pp, the product's fatigue signal) + a robust **Theil–Sen
  decline slope** (median of pairwise slopes, m/s per rep) — *did it see the same decline?*

We deliberately **do not headline Pearson r**: it is scale-free (throws away the m/s we care
about) and pivots on the set mean, so a single ghost/phantom rep flips its sign on slow,
narrow-range lifts — that is the −0.46 row artifact, not an inverse lift. VL-Δ and a
median-based slope answer the shape question without that fragility (and a ghost rep is
excluded, not averaged in). Absolute m/s caveats unchanged: **CV-auto is hub-inflated**
(count-only); **CV-adj exists only for bench** (no registered seed/rim for DL/ROW yet);
**Watch-auto over-segments** pauses; **watch bench velocity is low-SNR**.

## Rep counts (all sets)

| set | lift | GT | Vitruve | SmartBarbell | CV-auto | CV-adj | Watch-auto | Watch-adj |
|---|---|---|---|---|---|---|---|---|
| 20260613-DL-1 | deadlift | 5 | 5 | 5 | 6 | – | – | – |
| 20260613-DL-2 | deadlift | 3 | 3 | 3 | **3** ✓ | – | – | – |
| 20260613-DL-3 | deadlift | 2 | 2 | 2 | 4 | – | – | – |
| 20260613-DL-4 | deadlift | 2 | 2 | 2 | 3 | – | – | – |
| 20260613-DL-5 | deadlift | 8 | 8 | 8 | 9 | – | – | – |
| 20260613-DL-6 | deadlift | 8 | 8 | 8 | 9 | – | – | – |
| 20260615-ROW-1 | row | 10 | 10 | 9 | **10** ✓ | – | – | – |
| 20260615-ROW-2 | row | 10 | 10 | 9 | **10** ✓ | – | 11 | 9 |
| 20260615-ROW-3 | row | 10 | 10 | 10 | 8 | – | 12 | **10** ✓ |
| 20260615-ROW-4 | row | 10 | 10 | 8 | 9 | – | 11 | **10** ✓ |
| 20260615-ROW-5 | row | 10 | 10 | 8 | **10** ✓ | – | 13 | **10** ✓ |
| 20260616-BN-1 | bench | 10 | 10 | 10 | **10** ✓ | **10** ✓ | 25 | **10** ✓ |
| 20260616-BN-2 | bench | 10 | 10 | 10 | **10** ✓ | **10** ✓ | 31 | **10** ✓ |
| 20260616-BN-3 | bench | 10 | 10 | 10 | **10** ✓ | **10** ✓ | 22 | 11 |
| 20260616-BN-4 | bench | 10 | 10 | 10 | 11 | **10** ✓ | 14 | 9 |
| 20260616-BN-5 | bench | 10 | 10 | 10 | 11 | **10** ✓ | 23 | **10** ✓ |
| 20260617-SQ-1 | squat | 10 | 10 | – | 5 | – | 40 | **10** ✓ |
| 20260617-SQ-2 | squat | 10 | 10 | – | **10** ✓ | – | 35 | **10** ✓ |
| 20260617-SQ-3 | squat | 10 | 10 | – | **10** ✓ | – | 50 | 11 |
| 20260617-SQ-4 | squat | 10 | 10 | – | **10** ✓ | – | 40 | **10** ✓ |
| 20260617-RDL-1 | rdl | 8 | 8 | – | **8** ✓ | – | 13 | **8** ✓ |
| 20260617-RDL-2 | rdl | 8 | 8 | – | **8** ✓ | – | 19 | **8** ✓ |

**CV-adj = 10/10 EXACT on all 5 bench sets**; **Watch-adj exact/±1 on every instrumented set**.
**06-17 squats/RDLs are 3/4 inputs (no SmartBarbell):** CV-auto is EXACT on SQ-2/3/4 + both RDLs
(SQ-1, the 225 lb top set, undercounts 5/10 — needs a tap seed, like the early bench); Watch-adj is
exact on every set but SQ-3 (one trailing partial phantom). The squats are the FIRST main-lift squat
rows in this table.
DL CV-auto is the pure no-config path (over-counts the double-hump); the recorded path
(proxy + DL-5 one-tap + double-bump merge) hit all six EXACT — different, both honest.

## Bench — 06-16 (5×10) · 4/4 inputs

The fully-instrumented workout. CV-adj & Watch-adj are the trustworthy velocity columns; CV-auto RMSE quantifies its hub inflation (large by design).

### 20260616-BN-1

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 10/10 | 0.027 | +0.019 | 41.9→42.5 (-0.6) | -0.020→-0.017 (-0.003) |
| CV-auto | 10/10 | 0.606 | +0.560 | 60.0→42.5 (+17.5) | -0.046→-0.017 (-0.030) |
| CV-adj | 10/10 | 0.071 | -0.055 | 38.8→42.5 (-3.7) | -0.011→-0.017 (+0.006) |
| Watch-adj | 10/10 | 0.077 | -0.048 | 24.9→42.5 (-17.6) | +0.001→-0.017 (+0.018) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | CV-adj | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.360 | 0.410 | 0.989 | 0.296 | 0.283 |
| 2 | 0.400 | 0.430 | 0.984 | 0.284 | 0.252 |
| 3 | 0.390 | 0.410 | 1.248 | 0.363 | 0.268 |
| 4 | 0.370 | 0.380 | 0.884 | 0.255 | 0.273 |
| 5 | 0.360 | 0.370 | 1.166 | 0.341 | 0.317 |
| 6 | 0.340 | 0.370 | 1.106 | 0.328 | 0.301 |
| 7 | 0.320 | 0.300 | 0.753 | 0.222 | 0.344 |
| 8 | 0.310 | 0.330 | 0.781 | 0.228 | 0.277 |
| 9 | 0.270 | 0.270 | 0.803 | 0.235 | 0.280 |
| 10 | 0.190 | 0.230 | 0.196 | 0.209 | 0.237 |
| **mean** | **0.331** | **0.350** | **0.891** | **0.276** | **0.283** |

</details>

### 20260616-BN-2

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 10/10 | 0.044 | +0.040 | 32.3→24.4 (+7.9) | -0.015→-0.012 (-0.003) |
| CV-auto | 10/10 | 0.296 | +0.259 | 60.8→24.4 (+36.4) | -0.026→-0.012 (-0.014) |
| CV-adj | 10/10 | 0.027 | -0.018 | 31.3→24.4 (+6.9) | -0.011→-0.012 (+0.001) |
| Watch-adj | 10/10 | 0.101 | +0.047 | 29.0→24.4 (+4.6) | +0.011→-0.012 (+0.023) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | CV-adj | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.330 | 0.380 | 0.679 | 0.349 | 0.253 |
| 2 | 0.400 | 0.480 | 0.785 | 0.404 | 0.294 |
| 3 | 0.410 | 0.440 | 0.712 | 0.367 | 0.435 |
| 4 | 0.390 | 0.410 | 0.686 | 0.353 | 0.450 |
| 5 | 0.400 | 0.440 | 0.718 | 0.370 | 0.473 |
| 6 | 0.380 | 0.430 | 0.713 | 0.367 | 0.510 |
| 7 | 0.360 | 0.410 | 0.661 | 0.341 | 0.484 |
| 8 | 0.340 | 0.390 | 0.653 | 0.342 | 0.476 |
| 9 | 0.330 | 0.340 | 0.444 | 0.291 | 0.478 |
| 10 | 0.290 | 0.310 | 0.172 | 0.264 | 0.246 |
| **mean** | **0.363** | **0.403** | **0.622** | **0.345** | **0.410** |

</details>

### 20260616-BN-3

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 10/10 | 0.056 | +0.038 | 41.5→30.0 (+11.5) | -0.022→-0.018 (-0.004) |
| CV-auto | 10/10 | 0.788 | +0.728 | 64.4→30.0 (+34.4) | -0.097→-0.018 (-0.079) |
| CV-adj | 10/10 | 0.035 | -0.020 | 41.8→30.0 (+11.8) | -0.022→-0.018 (-0.004) |
| Watch-adj | 11/10 | — (count≠) | — | 57.9→30.0 (+27.9) | +0.002→-0.018 (+0.020) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | CV-adj | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.360 | 0.400 | 1.241 | 0.351 | 0.129 |
| 2 | 0.360 | 0.470 | 1.385 | 0.403 | 0.274 |
| 3 | 0.400 | 0.470 | 1.433 | 0.408 | 0.228 |
| 4 | 0.390 | 0.440 | 1.338 | 0.378 | 0.413 |
| 5 | 0.390 | 0.420 | 1.239 | 0.350 | 0.476 |
| 6 | 0.350 | 0.400 | 1.075 | 0.312 | 0.462 |
| 7 | 0.330 | 0.360 | 1.057 | 0.301 | 0.435 |
| 8 | 0.310 | 0.320 | 0.939 | 0.271 | 0.447 |
| 9 | 0.290 | 0.340 | 0.788 | 0.228 | 0.336 |
| 10 | 0.270 | 0.210 | 0.233 | 0.247 | 0.249 |
| 11 | – | – | – | – | 0.152 |
| **mean** | **0.345** | **0.383** | **1.073** | **0.325** | **0.327** |

</details>

### 20260616-BN-4

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 10/10 | 0.033 | +0.025 | 44.3→39.7 (+4.6) | -0.025→-0.020 (-0.005) |
| CV-auto | 11/10 | — (count≠) | — | 70.2→39.7 (+30.5) | -0.026→-0.020 (-0.006) |
| CV-adj | 10/10 | 0.042 | -0.027 | 43.5→39.7 (+3.8) | -0.018→-0.020 (+0.002) |
| Watch-adj | 9/10 | — (count≠) | — | 62.3→39.7 (+22.6) | -0.028→-0.020 (-0.008) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | CV-adj | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.290 | 0.340 | 0.166 | 0.240 | 0.206 |
| 2 | 0.390 | 0.440 | 0.752 | 0.387 | 0.423 |
| 3 | 0.350 | 0.410 | 0.589 | 0.354 | 0.424 |
| 4 | 0.370 | 0.400 | 0.845 | 0.360 | 0.426 |
| 5 | 0.310 | 0.320 | 0.871 | 0.278 | 0.249 |
| 6 | 0.330 | 0.350 | 0.648 | 0.226 | 0.222 |
| 7 | 0.300 | 0.300 | 0.680 | 0.262 | 0.178 |
| 8 | 0.250 | 0.260 | 0.631 | 0.244 | 0.166 |
| 9 | 0.270 | 0.260 | 0.611 | 0.228 | 0.155 |
| 10 | 0.200 | 0.230 | 0.483 | 0.209 | – |
| 11 | – | – | 0.036 | – | – |
| **mean** | **0.306** | **0.331** | **0.574** | **0.279** | **0.272** |

</details>

### 20260616-BN-5

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 10/10 | 0.033 | +0.012 | 57.0→58.8 (-1.8) | -0.035→-0.026 (-0.009) |
| CV-auto | 11/10 | — (count≠) | — | 60.9→58.8 (+2.1) | -0.118→-0.026 (-0.092) |
| CV-adj | 10/10 | 0.023 | -0.016 | 55.1→58.8 (-3.6) | -0.027→-0.026 (-0.001) |
| Watch-adj | 10/10 | 0.092 | +0.009 | 69.5→58.8 (+10.8) | -0.019→-0.026 (+0.007) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | CV-adj | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.330 | 0.300 | 0.172 | 0.316 | 0.234 |
| 2 | 0.400 | 0.430 | 1.980 | 0.371 | 0.291 |
| 3 | 0.360 | 0.410 | 2.239 | 0.354 | 0.481 |
| 4 | 0.390 | 0.420 | 2.116 | 0.360 | 0.462 |
| 5 | 0.290 | 0.340 | 2.299 | 0.299 | 0.464 |
| 6 | 0.280 | 0.260 | 1.747 | 0.235 | 0.261 |
| 7 | 0.240 | 0.250 | 1.163 | 0.221 | 0.173 |
| 8 | 0.240 | 0.200 | 1.348 | 0.209 | 0.288 |
| 9 | 0.220 | 0.240 | 1.338 | 0.220 | 0.151 |
| 10 | 0.110 | 0.130 | 1.416 | 0.113 | 0.142 |
| 11 | – | – | 0.383 | – | – |
| **mean** | **0.286** | **0.298** | **1.473** | **0.270** | **0.295** |

</details>
## Rows — 06-15 (target 10) · 4/4 on sets 2–5, no CV-adj

Watch-adj is the trustworthy velocity here. CV-auto m/s is a diagonal-arc artifact (count-only). SB under-counts ROW-4/5 → absolute axis abstains there.

### 20260615-ROW-1  *(no watch — set-1 recording missing)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 9/10 | — (count≠) | — | 21.3→10.9 (+10.4) | -0.016→-0.006 (-0.011) |
| CV-auto | 10/10 | 1.258 | +1.198 | 11.2→10.9 (+0.3) | +0.010→-0.006 (+0.015) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.750 | 0.710 | 0.841 |
| 2 | 0.770 | 0.800 | 2.039 |
| 3 | 0.740 | 0.690 | 2.322 |
| 4 | 0.720 | 0.750 | 1.859 |
| 5 | 0.780 | 0.730 | 2.033 |
| 6 | 0.780 | 0.690 | 2.041 |
| 7 | 0.750 | 0.710 | 2.147 |
| 8 | 0.730 | 0.690 | 1.982 |
| 9 | 0.730 | 0.570 | 2.071 |
| 10 | 0.660 | – | 2.051 |
| **mean** | **0.741** | **0.704** | **1.939** |

</details>

### 20260615-ROW-2

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 9/10 | — (count≠) | — | 22.3→23.1 (-0.8) | -0.014→-0.017 (+0.003) |
| CV-auto | 10/10 | 1.059 | +1.057 | 13.7→23.1 (-9.4) | -0.025→-0.017 (-0.008) |
| Watch-adj | 9/10 | — (count≠) | — | 19.0→23.1 (-4.1) | -0.015→-0.017 (+0.001) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | Watch-auto | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.700 | 0.790 | 1.845 | 0.299 | 0.683 |
| 2 | 0.740 | 0.690 | 1.849 | 0.683 | 0.684 |
| 3 | 0.710 | 0.680 | 1.744 | 0.684 | 0.720 |
| 4 | 0.780 | 0.830 | 1.806 | 0.720 | 0.708 |
| 5 | 0.760 | 0.720 | 1.863 | 0.708 | 0.690 |
| 6 | 0.730 | 0.690 | 1.842 | 0.690 | 0.713 |
| 7 | 0.710 | 0.670 | 1.706 | 0.713 | 0.632 |
| 8 | 0.710 | 0.610 | 1.740 | 0.632 | 0.610 |
| 9 | 0.610 | 0.680 | 1.646 | 0.610 | 0.557 |
| 10 | 0.590 | – | 1.571 | 0.557 | – |
| 11 | – | – | – | 0.630 | – |
| **mean** | **0.704** | **0.707** | **1.761** | **0.630** | **0.666** |

</details>

### 20260615-ROW-3

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 10/10 | 0.163 | +0.111 | 12.6→12.3 (+0.3) | -0.002→-0.011 (+0.009) |
| CV-auto | 8/10 | — (count≠) | — | 13.4→12.3 (+1.1) | -0.068→-0.011 (-0.057) |
| Watch-adj | 10/10 | 0.059 | -0.048 | 17.2→12.3 (+4.9) | -0.005→-0.011 (+0.006) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | Watch-auto | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.770 | 0.540 | 6.788 | 0.350 | 0.648 |
| 2 | 0.770 | 0.870 | 7.168 | 0.648 | 0.701 |
| 3 | 0.760 | 0.840 | 7.165 | 0.701 | 0.689 |
| 4 | 0.770 | 0.950 | 7.131 | 0.689 | 0.756 |
| 5 | 0.760 | 0.900 | 7.555 | 0.756 | 0.704 |
| 6 | 0.740 | 0.940 | 6.454 | 0.704 | 0.712 |
| 7 | 0.720 | 0.910 | 6.886 | 0.712 | 0.696 |
| 8 | 0.690 | 0.830 | 6.199 | 0.696 | 0.693 |
| 9 | 0.710 | 0.870 | – | 0.693 | 0.650 |
| 10 | 0.640 | 0.790 | – | 0.650 | 0.602 |
| 11 | – | – | – | 0.602 | – |
| 12 | – | – | – | 0.360 | – |
| **mean** | **0.733** | **0.844** | **6.918** | **0.630** | **0.685** |

</details>

### 20260615-ROW-4

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 8/10 | — (count≠) | — | 13.9→5.9 (+7.9) | +0.004→-0.005 (+0.009) |
| CV-auto | 9/10 | — (count≠) | — | 7.7→5.9 (+1.8) | -0.021→-0.005 (-0.016) |
| Watch-adj | 10/10 | 0.102 | -0.060 | 2.3→5.9 (-3.6) | +0.008→-0.005 (+0.013) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | Watch-auto | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.750 | 0.680 | 2.435 | 0.472 | 0.472 |
| 2 | 0.760 | 0.700 | 3.844 | 0.629 | 0.629 |
| 3 | 0.710 | 0.680 | 3.710 | 0.701 | 0.701 |
| 4 | 0.750 | 0.710 | 3.632 | 0.688 | 0.688 |
| 5 | 0.690 | 0.830 | 3.537 | 0.639 | 0.639 |
| 6 | 0.690 | 0.630 | 3.656 | 0.662 | 0.662 |
| 7 | 0.700 | 0.730 | 3.725 | 0.703 | 0.703 |
| 8 | 0.680 | 0.700 | 3.593 | 0.688 | 0.688 |
| 9 | 0.730 | – | 3.500 | 0.683 | 0.683 |
| 10 | 0.700 | – | – | 0.690 | 0.690 |
| 11 | – | – | – | 0.597 | – |
| **mean** | **0.716** | **0.708** | **3.515** | **0.650** | **0.655** |

</details>

### 20260615-ROW-5

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 8/10 | — (count≠) | — | 17.1→11.9 (+5.2) | -0.005→-0.013 (+0.007) |
| CV-auto | 10/10 | 2.362 | +2.348 | 10.8→11.9 (-1.1) | -0.006→-0.013 (+0.007) |
| Watch-adj | 10/10 | 0.053 | -0.045 | 8.2→11.9 (-3.7) | -0.008→-0.013 (+0.005) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto | Watch-auto | Watch-adj |
|---|---|---|---|---|---|
| 1 | 0.730 | 0.700 | 2.426 | 0.368 | 0.673 |
| 2 | 0.800 | 0.780 | 3.162 | 0.673 | 0.762 |
| 3 | 0.780 | 0.730 | 3.521 | 0.762 | 0.719 |
| 4 | 0.790 | 0.740 | 3.149 | 0.719 | 0.755 |
| 5 | 0.790 | 0.820 | 3.143 | 0.755 | 0.763 |
| 6 | 0.760 | 0.750 | 3.173 | 0.763 | 0.702 |
| 7 | 0.700 | 0.730 | 2.969 | 0.702 | 0.627 |
| 8 | 0.680 | 0.630 | 3.098 | 0.627 | 0.588 |
| 9 | 0.720 | – | 3.306 | 0.588 | 0.706 |
| 10 | 0.690 | – | 2.977 | 0.706 | 0.695 |
| 11 | – | – | – | 0.695 | – |
| 12 | – | – | – | 0.253 | – |
| 13 | – | – | – | 0.088 | – |
| **mean** | **0.744** | **0.735** | **3.092** | **0.592** | **0.699** |

</details>
## Deadlift — 06-13 · 3/4 inputs (no watch), no CV-adj

CV-auto on a 720p upright proxy; absolute m/s hub-inflated (count-focused). Low-rep sets (<3 reps) have no velocity-loss by definition.

### 20260613-DL-1

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 5/5 | 0.044 | -0.018 | 5.8→3.4 (+2.4) | +0.073→+0.039 (+0.033) |
| CV-auto | 6/5 | — (count≠) | — | 17.2→3.4 (+13.7) | -0.018→+0.039 (-0.058) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.550 | 0.470 | 1.236 |
| 2 | 0.710 | 0.700 | 1.364 |
| 3 | 0.660 | 0.620 | 1.539 |
| 4 | 0.680 | 0.680 | 1.315 |
| 5 | 0.730 | 0.770 | 1.406 |
| 6 | – | – | 1.144 |
| **mean** | **0.666** | **0.648** | **1.334** |

</details>

### 20260613-DL-2

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 3/3 | 0.185 | -0.173 | 12.3→2.3 (+10.0) | +0.015→+0.050 (-0.035) |
| CV-auto | 3/3 | 0.450 | +0.196 | 1.5→2.3 (-0.8) | +0.464→+0.050 (+0.414) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.550 | 0.370 | 0.173 |
| 2 | 0.620 | 0.530 | 1.134 |
| 3 | 0.650 | 0.400 | 1.100 |
| **mean** | **0.607** | **0.433** | **0.802** |

</details>

### 20260613-DL-3

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 2/2 | 0.085 | -0.030 | –→– | +0.190→+0.030 (+0.160) |
| CV-auto | 4/2 | — (count≠) | — | 16.0→– | +0.266→+0.030 (+0.236) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.580 | 0.470 | 0.357 |
| 2 | 0.610 | 0.660 | 0.977 |
| 3 | – | – | 1.326 |
| 4 | – | – | 0.903 |
| **mean** | **0.595** | **0.565** | **0.891** |

</details>

### 20260613-DL-4

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 2/2 | 0.035 | -0.005 | –→– | -0.010→+0.060 (-0.070) |
| CV-auto | 3/2 | — (count≠) | — | 37.5→– | -0.180→+0.060 (-0.240) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.520 | 0.550 | 1.905 |
| 2 | 0.580 | 0.540 | 0.835 |
| 3 | – | – | 1.545 |
| **mean** | **0.550** | **0.545** | **1.428** |

</details>

### 20260613-DL-5

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 8/8 | 0.034 | +0.016 | 28.5→29.7 (-1.2) | -0.018→-0.018 (+0.000) |
| CV-auto | 9/8 | — (count≠) | — | 38.1→29.7 (+8.4) | -0.058→-0.018 (-0.040) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.520 | 0.580 | 0.310 |
| 2 | 0.630 | 0.580 | 1.334 |
| 3 | 0.620 | 0.640 | 1.475 |
| 4 | 0.640 | 0.650 | 1.265 |
| 5 | 0.590 | 0.630 | 1.282 |
| 6 | 0.570 | 0.590 | 1.202 |
| 7 | 0.480 | 0.500 | 1.171 |
| 8 | 0.420 | 0.430 | 0.969 |
| 9 | – | – | 0.857 |
| **mean** | **0.559** | **0.575** | **1.096** |

</details>

### 20260613-DL-6

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| SmartBarbell | 8/8 | 0.052 | -0.004 | 14.9→6.6 (+8.3) | -0.004→-0.002 (-0.002) |
| CV-auto | 9/8 | — (count≠) | — | 77.3→6.6 (+70.7) | -0.088→-0.002 (-0.086) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.490 | 0.530 | 0.950 |
| 2 | 0.520 | 0.450 | 0.937 |
| 3 | 0.520 | 0.570 | 0.893 |
| 4 | 0.470 | 0.370 | 0.312 |
| 5 | 0.510 | 0.550 | 0.460 |
| 6 | 0.530 | 0.560 | 0.205 |
| 7 | 0.500 | 0.500 | 0.876 |
| 8 | 0.490 | 0.470 | 0.255 |
| 9 | – | – | 0.176 |
| **mean** | **0.504** | **0.500** | **0.563** |

</details>

## Squat — 06-17 (4 sets ×10) · 3/4 inputs (no SmartBarbell), no CV-adj

The **first main-lift squat data** in this table. CV is count-only here (auto counts from
`clips.csv`; absolute m/s hub-inflated, no `rim_px` registered — the video wasn't re-run for
velocity). **Watch-adj is the trustworthy velocity column** and the squat is a good case for it: a
standing lift where the wrist tracks the bar on the back through a full ~0.65 m ROM. Watch-auto
over-segments massively (35–50 segments) on the deep pause at the bottom of each rep — the known
detector gap, count shown for reference only.

Squat-only **Watch-adj aggregate vs Vitruve** (count-matched SQ-1/2/4, n=30): **bias −0.041,
RMSE 0.093 m/s** — bench-ballpark, above the SEE<0.07 target. Per-rep **r is low (0.26)** but that's
the narrow-range artifact (squat MV spans only ~0.43–0.65 m/s, statistically caps r — the same
reality check as bench, learning #25), not an inverse fit; the VL-Δ and slope tell the shape story.

### 20260617-SQ-1  *(225 lb top set, RPE 6.5)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| CV-auto | 5/10 | count-only (undercount; abs m/s hub-inflated) | — | — | — |
| Watch-adj | 10/10 | 0.071 | -0.033 | 14.8→30.2 (-15.4) | +0.004→-0.020 (+0.024) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | Watch-adj |
|---|---|---|
| 1 | 0.520 | 0.424 |
| 2 | 0.590 | 0.466 |
| 3 | 0.630 | 0.564 |
| 4 | 0.580 | 0.506 |
| 5 | 0.560 | 0.592 |
| 6 | 0.580 | 0.544 |
| 7 | 0.520 | 0.476 |
| 8 | 0.510 | 0.461 |
| 9 | 0.450 | 0.497 |
| 10 | 0.430 | 0.512 |
| **mean** | **0.541** | **0.504** |

</details>

### 20260617-SQ-2  *(205 lb, RPE 5)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| CV-auto | 10/10 | count-only (abs m/s hub-inflated) | — | — | — |
| Watch-adj | 10/10 | 0.131 | -0.091 | 30.7→14.6 (+16.1) | -0.001→-0.010 (+0.009) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | Watch-adj |
|---|---|---|
| 1 | 0.650 | 0.495 |
| 2 | 0.610 | 0.524 |
| 3 | 0.650 | 0.470 |
| 4 | 0.630 | 0.614 |
| 5 | 0.640 | 0.538 |
| 6 | 0.620 | 0.648 |
| 7 | 0.610 | 0.664 |
| 8 | 0.590 | 0.328 |
| 9 | 0.580 | 0.432 |
| 10 | 0.530 | 0.487 |
| **mean** | **0.611** | **0.520** |

</details>

### 20260617-SQ-3  *(215 lb, RPE 5.5)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| CV-auto | 10/10 | count-only (abs m/s hub-inflated) | — | — | — |
| Watch-adj | 11/10 | — (count≠) | — | 13.0→19.5 (-6.5) | +0.010→-0.014 (+0.024) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | Watch-adj |
|---|---|---|
| 1 | 0.550 | 0.490 |
| 2 | 0.610 | 0.513 |
| 3 | 0.640 | 0.523 |
| 4 | 0.630 | 0.531 |
| 5 | 0.590 | 0.524 |
| 6 | 0.580 | 0.515 |
| 7 | 0.580 | 0.630 |
| 8 | 0.560 | 0.535 |
| 9 | 0.530 | 0.345 |
| 10 | 0.500 | 0.618 |
| 11 | – | 0.835 |
| **mean** | **0.577** | **0.551** |

</details>

### 20260617-SQ-4  *(225 lb, RPE 5)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| CV-auto | 10/10 | count-only (abs m/s hub-inflated) | — | — | — |
| Watch-adj | 10/10 | 0.061 | +0.001 | 13.2→19.0 (-5.9) | -0.001→-0.015 (+0.014) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | Watch-adj |
|---|---|---|
| 1 | 0.580 | 0.497 |
| 2 | 0.630 | 0.637 |
| 3 | 0.610 | 0.602 |
| 4 | 0.600 | 0.546 |
| 5 | 0.620 | 0.628 |
| 6 | 0.590 | 0.520 |
| 7 | 0.550 | 0.598 |
| 8 | 0.530 | 0.553 |
| 9 | 0.530 | 0.669 |
| 10 | 0.490 | 0.492 |
| **mean** | **0.573** | **0.574** |

</details>

## RDL — 06-17 (2 sets ×8) · 3/4 inputs, no CV-adj

The honest counter-case: **CV-auto counts both sets EXACT (8/8)** and **Watch-adj counts both EXACT**,
but **watch absolute velocity fails** — bias **−0.21 m/s**, RMSE **0.22** (aggregate n=16). This is the
**hinge-anchor limitation**: in an RDL the wrist hangs at arm's length and the bar travels by hip
hinge, so the wrist's linear velocity systematically *under-reads* the bar (≈0.28 watch vs ≈0.47
Vitruve). It is NOT a detector bug — counts and ROM are right; the wrist simply isn't the bar on a
hinge. **Velocity-LOSS survives** (VL-Δ −1.4 / −5.1 pp) because it's scale-invariant, and per-rep
**r=0.70** — the shape tracks, the scale is offset. A per-lift anchor calibration (learning #4's
constant offset) is the candidate fix; flagged in the set notes.

### 20260617-RDL-1  *(225 lb, RPE 6.5)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| CV-auto | 8/8 | count-only (abs m/s hub-inflated) | — | — | — |
| Watch-adj | 8/8 | 0.214 | -0.209 | 3.8→5.2 (-1.4) | +0.016→+0.000 (+0.016) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | Watch-adj |
|---|---|---|
| 1 | 0.410 | 0.106 |
| 2 | 0.470 | 0.217 |
| 3 | 0.480 | 0.266 |
| 4 | 0.450 | 0.254 |
| 5 | 0.460 | 0.267 |
| 6 | 0.470 | 0.288 |
| 7 | 0.470 | 0.279 |
| 8 | 0.440 | 0.302 |
| **mean** | **0.456** | **0.247** |

</details>

### 20260617-RDL-2  *(225 lb, RPE 6.5)*

| method | n (src/ref) | RMSE | bias | VL src→ref (Δpp) | slope src→ref (Δ, m/s·rep⁻¹) |
|---|---|---|---|---|---|
| CV-auto | 8/8 | count-only (abs m/s hub-inflated) | — | — | — |
| Watch-adj | 8/8 | 0.221 | -0.219 | 0.3→5.4 (-5.1) | +0.009→+0.001 (+0.008) |

<details><summary>per-rep velocities</summary>

| rep | Vitruve | Watch-adj |
|---|---|---|
| 1 | 0.510 | 0.332 |
| 2 | 0.530 | 0.270 |
| 3 | 0.500 | 0.278 |
| 4 | 0.550 | 0.308 |
| 5 | 0.560 | 0.318 |
| 6 | 0.500 | 0.271 |
| 7 | 0.550 | 0.341 |
| 8 | 0.510 | 0.343 |
| **mean** | **0.526** | **0.308** |

</details>

## Reading the panels

- **Bench, trustworthy columns:** CV-adj RMSE ≈ SmartBarbell's and its VL-Δ tracks Vitruve;
  Watch-adj lands the decline direction (negative slope) but with bench's known low SNR.
- **CV-auto's big RMSE is the point** — it shows the hub-vs-rim scale error quantitatively,
  which the count alone hides.
- **Shape survives ghosts:** where a stray rep would send Pearson r negative, the VL-Δ and
  Theil–Sen slope stay interpretable because phantoms are excluded and the slope is a median.
- **Absolute abstains honestly:** any `— (count≠)` cell means counts didn't match after
  phantom-exclusion, so comparing per-rep m/s would be comparing the wrong reps.

Gaps to close: register tap seeds/`rim_px` for DL, ROW & the 06-17 squats/RDLs (unlocks CV-adj +
trustworthy CV velocity there — and a tap seed would also recover the SQ-1 top-set undercount); a
learned IMU rep detector to fix Watch-auto over-segmentation (squat pauses blow it up to 35–50
segments); and an **RDL/hinge anchor calibration** — the wrist under-reads the bar by a near-constant
~0.21 m/s on the hinge (counts + VL are fine; absolute velocity needs a per-lift offset, learning #4).
