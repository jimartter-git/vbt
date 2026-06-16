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

### CSV format (PoC default)

Header row, then one sample per line, comma-separated, in this exact column
order:

```
t,ua_x,ua_y,ua_z,g_x,g_y,g_z,q_w,q_x,q_y,q_z
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

Each recorded set produces one CSV file plus a small JSON sidecar of metadata:

```json
{
  "schemaVersion": 2,
  "sessionId": "UUID",
  "startedAt": "ISO-8601 UTC at record START (the wall-clock anchor)",
  "clockAnchorUptimeSeconds": 15463.1,
  "exercise": "deadlift",
  "sampleRateHintHz": 200,
  "deviceModel": "Watch6,18",
  "watchOSVersion": "10.x",
  "sampleCount": 12345,
  "notes": "optional free text (load, set #, RPE)"
}
```

`startedAt` + `clockAnchorUptimeSeconds` are a contemporaneous `(UTC, device-uptime)`
pair captured at record start — the only thing that ties the uptime-based sample
`t` to absolute time. **v2** added `clockAnchorUptimeSeconds` (v1 had `startedAt`
only, set at *write* time → unusable as an anchor).

Filename convention (v2): **`VBT_<yyyy-MM-dd_HHmmss>Z_<exercise>_<short-id>`**, e.g.
`VBT_2026-06-15_182203Z_deadlift_CE3E8765.csv` — sortable + legible in the phone's
session list (v1 used the bare `<sessionId>` UUID, which is unorderable and caused
the 06-15 row files to be mislabeled).

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
