# Data Schema — the recording contract

This is the single contract shared by the watch (producer), the phone
(relay/persistence), and the Python analysis pipeline (consumer). Keep this
doc and `Packages/VBTCore/Sources/VBTCore/MotionSample.swift` in lock-step.

## Raw motion sample

One row per `CMDeviceMotion` sample. Captured on watchOS via
`CMBatchedSensorManager` (target ~200 Hz on Series 8 / SE2 / Ultra).

| field          | unit                | source (`CMDeviceMotion`)        |
|----------------|---------------------|----------------------------------|
| `t`            | seconds (monotonic) | `.timestamp` (device uptime)     |
| `ua_x/y/z`     | g (gravity removed) | `.userAcceleration`              |
| `g_x/y/z`      | g (unit-ish)        | `.gravity`                       |
| `q_w/x/y/z`    | quaternion          | `.attitude.quaternion`           |
| `rr_x/y/z` †   | rad/s               | `.rotationRate` (calibrated gyro)|
| `mf_x/y/z` †   | µT                  | `.magneticField.field` (calibrated; accuracy varies) |

† **Optional, appended later.** `rr_*` (gyro) and `mf_*` (magnetometer) were added
after the first captures, so they are **not required**: recordings predating them
lack the columns, and both the Swift decoder (`MotionSampleCSV`) and the Python
loader (`ingest.load_session`, `OPTIONAL_COLUMNS`) default them to 0 when absent
(`ingest.has_gyro()` reports whether a session carries a real gyro signal). The
**gyro is the high-value addition** — it enables orientation fusion (a real
Madgwick AHRS, which Apple's pre-fused `g`/`q` made untestable on the original
schema) and is the richest feature for a future learned rep/velocity model. The
magnetometer is logged opportunistically (its indoor/gym accuracy is often poor).

### CSV format (PoC default)

Header row, then one sample per line, comma-separated, in this exact column
order (the optional gyro/mag columns are kept **at the end** so older 11-column
files still parse by name):

```
t,ua_x,ua_y,ua_z,g_x,g_y,g_z,q_w,q_x,q_y,q_z,rr_x,rr_y,rr_z,mf_x,mf_y,mf_z
```

- `t` is `CMDeviceMotion.timestamp` (seconds since device boot). It is monotonic
  but **not** wall-clock and **not** comparable across devices — only deltas
  within one recording are meaningful. **To recover absolute UTC** for fusion
  (lining the watch up against video/Vitruve), use the envelope's clock anchor:
  `sampleUTC = startedAt + (t − clockAnchorUptimeSeconds)`. Coarse cross-source
  sync comes free from the UTC anchor; the precise sub-second offset is then
  refined by **velocity cross-correlation** (`analysis/scripts/_align_matrix.py`)
  — the watch↔video clocks are independent, so signal alignment is the source of
  truth (the 06-15 rows aligned at a consistent ~+2 s lag, r up to 0.97).
- CSV is chosen for PoC volumes (a 45-min session at 200 Hz ≈ 540k rows ≈ tens
  of MB) because it is trivially `pandas.read_csv`-able and human-eyeballable.
  A length-prefixed binary format is the documented upgrade path once the
  signal is proven; `VBTCore` will own both encoders behind one type.

## Session envelope

The watch produces **two kinds of files during one workout**, both carrying
the same `workoutId` so an analysis tool can group them without touching
HealthKit:

- One `**workoutHR**` file per workout: the workout-wide 1 Hz HR stream.
  Filename `<YYYYMMDD>-workout_hr.csv` + sidecar.
- One `**velocitySet**` file per tagged set: the IMU sample stream for that
  set. Filename `<YYYYMMDD>-<LIFT>-<N>_watch.csv` + sidecar (matches the
  existing `dataset/raw/` convention).

Both share this JSON sidecar shape:

```json
{
  "schemaVersion": 3,
  "sessionId": "UUID (unique per file)",
  "workoutId": "UUID (shared across all files from one workout)",
  "kind": "velocitySet | workoutHR",
  "startedAt": "ISO-8601 UTC at record START",
  "stoppedAt": "ISO-8601 UTC at record STOP",
  "clockAnchorUptimeSeconds": 15463.1,
  "exercise": "bench | workout_hr | ...",
  "setMetadata": {
    "lift": "bench",
    "customLiftCode": null,
    "setIndex": 3,
    "mount": "wrist",
    "rpe": 8.0,
    "load": 205,
    "loadUnit": "lb",
    "plateType": "deepDish",
    "notes": null
  },
  "sampleRateHintHz": 200,
  "deviceModel": "Watch6,18",
  "watchOSVersion": "10.x",
  "sampleCount": 12345,
  "notes": "optional free text"
}
```

`startedAt` + `clockAnchorUptimeSeconds` are a contemporaneous
`(UTC, device-uptime)` pair captured at record start — the only thing that
ties the uptime-based sample `t` to absolute time. `stoppedAt` closes the
window so per-set HR slicing (`HRR30/60/90`, peak-in-set, session TRIMP) is a
one-liner. `setMetadata` is present on `velocitySet` files and null on
`workoutHR` files.

### Filename convention

| kind          | stem                                | example                        |
|---------------|-------------------------------------|--------------------------------|
| `velocitySet` | `<YYYYMMDD>-<LIFT>-<N>_watch`       | `20260706-BN-3_watch.csv`      |
| `workoutHR`   | `<YYYYMMDD>-workout_hr[-K]`         | `20260706-workout_hr.csv`      |

`LIFT` codes: `SQ`, `BN`, `DL`, `IB`, `ROW`, `RDL`, `SC`, or a user-typed code
when the lift is `.other`. `N` is 1-indexed **within that lift-day** — a second
workout on the same date reusing the same lift continues the count (`20260706-
BN-4` follows `20260706-BN-3`). A second workout the same date gets a `-K`
suffix on the HR file (`20260706-workout_hr-2`).

**Schema history**: **v1** had `startedAt` set at write time (unusable as an
anchor). **v2** added `clockAnchorUptimeSeconds` and the sortable stem
`VBT_<yyyy-MM-dd_HHmmss>Z_<exercise>_<short-id>`. **v3** introduced the
two-tier record model (`workoutId`, `kind`, `stoppedAt`, `setMetadata`) and
switched `velocitySet` files to the `<YYYYMMDD>-<LIFT>-<N>_watch` stem that
matches the dataset convention.

## Workout HR sample

One row per HR reading (~1 Hz during a workout, whatever HealthKit publishes).

| field | unit          | source                              |
|-------|---------------|-------------------------------------|
| `t`   | s (uptime)    | derived (wall-clock offset + anchor)|
| `utc` | ISO-8601      | `HKQuantitySample.startDate`        |
| `bpm` | beats/minute  | `.quantity` in `count/min`          |

Both `t` and `utc` are stored so slicing works from either axis — `t` aligns
natively with the IMU samples' `t`, `utc` is robust if the clock anchor is
ever lost.

## Derived metrics (analysis output — the cross-source contract)

This is the shape every `VelocitySource` (watch IMU, BLE, video) must emit so
the rep + fatigue model is source-agnostic:

```
RepMetrics {
  repIndex:        Int
  startTime:       seconds (relative to recording)
  turnaroundTime:  seconds   // bottom→top transition (the ZVU anchor)
  endTime:         seconds
  meanConcentricVelocity: m/s
  peakConcentricVelocity: m/s
  rangeOfMotion:   meters    // estimate; see architecture.md on ROM caveats
}

SetSummary {
  reps:            [RepMetrics]
  velocityLossPct: Double     // CANONICAL loss: (best MV − terminal MV) / best MV,
                              // terminal = mean of the last min(2, n−1) reps; 0 when
                              // n < 3. One definition everywhere — keep in lock-step
                              // with analysis/vbt_analysis/metrics.py
}
```
