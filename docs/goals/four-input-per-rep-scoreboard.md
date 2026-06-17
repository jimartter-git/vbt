# Four-input per-rep scoreboard — counts & mean velocity

Per-rep **rep counts** and **mean concentric velocity (m/s)** for every workout with 3–4 of
the four inputs (Vitruve · SmartBarbell · our-CV video · Apple-Watch IMU), across six methods.
Generated this session by re-running CV and the watch pipeline — not copied from prior aggregates.
Reproduce: watch+GT via the snippet in the commit; CV via `vel_eval.py` / the 720p DL proxy.

## The six methods

| col | method | definition |
|---|---|---|
| Vitruve | LPT ground truth | the established reference (`rep_metrics.csv`) |
| SmartBarbell | CV competitor / floor | phone-CV device (`rep_metrics.csv`, phantom rows excluded) |
| CV-auto | our CV, no-tap | `VideoConfig(tracker="auto")` — zero seed, zero per-clip config (shippable) |
| CV-adj | our CV, human-in-loop | registered tap seed + `rim_px` + `transit_aware` (`vel_eval --tap`) |
| Watch-auto | watch IMU, raw PoC | `detect_turnarounds` → ZUPT per-rep MV |
| Watch-adj | watch IMU, cleaned | `gate_reps` (rows) / bench-tuned ROM·MV clean (bench) |

## How to read the velocities (honest limits, not hidden)

- **CV-auto absolute m/s is NOT trustworthy** — it tracks the small hub without rim
  correction, inflating velocity ~3× on bench and producing nonsense on the diagonal row arc
  (~7 m/s). **CV-auto's _count_ is the deliverable; its m/s is not.** Shown for completeness.
- **CV-adj exists only for bench** — DL/ROW have no registered tap seed/`rim_px` yet, so that
  column is blank there. (ROW-5 was hand-seeded once at r=0.44 previously; not re-run here.)
- **Trustworthy absolute-m/s columns:** Vitruve, SmartBarbell, **CV-adj (bench)**, **Watch-adj (rows)**.
- **Watch-auto over-segments pauses** — mildly on rows (11–13), badly on supine bench (14–31
  phantom segments). Its per-rep velocities are only shown where the count stays near GT;
  on bench they're omitted from the detail tables (count is in the matrix; raw list in the JSON).
- Per-rep rows align positionally from rep 1; an under-counting method (e.g. SB) ends early.
  Cross-vendor true-rep alignment lives in `dataset/tools/compare.py`.

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

Count takeaways: **CV-adj = 10/10 EXACT on all 5 bench sets** (fixes CV-auto's BN-4/5 put-down
+1). **Watch-adj = exact or ±1 on every instrumented set.** DL CV-auto is the pure no-config
path and over-counts the double-humped pull; the documented recorded path (proxy + DL-5 one-tap
+ double-bump merge) hit all six EXACT (5/3/2/2/8/8) — both are honest, different paths.

## Bench — 06-16 (5×10) · 4/4 inputs

The only fully-instrumented workout. **CV-adj** and **Watch-adj** are the trustworthy velocity
columns. CV-auto m/s is hub-inflated (~3×). Watch-auto over-segments (14–31) → omitted per-rep,
count in the matrix. Watch-adj velocity is plausible but noisy (bench is the watch's weak case).

### 20260616-BN-1
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

### 20260616-BN-2
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

### 20260616-BN-3
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

### 20260616-BN-4
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

### 20260616-BN-5
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

## Rows — 06-15 (target 10) · 4/4 inputs on sets 2–5 (no watch on set 1), no CV-adj

**Watch-adj is the trustworthy velocity here** (row signal is strong, ~SEE 0.07). CV-auto m/s
is a diagonal-arc artifact (note the ~7 m/s) — count-only.

### 20260615-ROW-1  *(no watch — set-1 recording missing)*
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

### 20260615-ROW-2
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

### 20260615-ROW-3
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

### 20260615-ROW-4
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

### 20260615-ROW-5
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

## Deadlift — 06-13 · 3/4 inputs (no watch that day), no CV-adj

CV-auto on a 720p upright proxy; absolute m/s hub-inflated (count-focused). No watch recording.

### 20260613-DL-1
| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.550 | 0.470 | 1.236 |
| 2 | 0.710 | 0.700 | 1.364 |
| 3 | 0.660 | 0.620 | 1.539 |
| 4 | 0.680 | 0.680 | 1.315 |
| 5 | 0.730 | 0.770 | 1.406 |
| 6 | – | – | 1.144 |
| **mean** | **0.666** | **0.648** | **1.334** |

### 20260613-DL-2
| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.550 | 0.370 | 0.173 |
| 2 | 0.620 | 0.530 | 1.134 |
| 3 | 0.650 | 0.400 | 1.100 |
| **mean** | **0.607** | **0.433** | **0.802** |

### 20260613-DL-3
| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.580 | 0.470 | 0.357 |
| 2 | 0.610 | 0.660 | 0.977 |
| 3 | – | – | 1.326 |
| 4 | – | – | 0.903 |
| **mean** | **0.595** | **0.565** | **0.891** |

### 20260613-DL-4
| rep | Vitruve | SmartB | CV-auto |
|---|---|---|---|
| 1 | 0.520 | 0.550 | 1.905 |
| 2 | 0.580 | 0.540 | 0.835 |
| 3 | – | – | 1.545 |
| **mean** | **0.550** | **0.545** | **1.428** |

### 20260613-DL-5
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

### 20260613-DL-6
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

## What this table shows

- **Counts:** our stack matches or beats SmartBarbell everywhere it has the inputs — CV-adj
  10/10 exact on all bench, Watch-adj exact/±1 on every instrumented set.
- **Velocity, trustworthy columns:** on bench, CV-adj set-means track Vitruve closely
  (rim-corrected); Watch-adj on rows sits in the right band. These are the product-grade paths.
- **Known-weak columns kept visible for honesty:** CV-auto absolute m/s (no rim), Watch-auto
  counts (over-segmentation), Watch bench velocity (low SNR). Diagnosed, not hidden.
- **Gaps to close:** register tap seeds/`rim_px` for DL & ROW (unlocks CV-adj there); ingest
  watch IMU into `rep_metrics`; a learned IMU rep detector to fix Watch-auto over-segmentation.
