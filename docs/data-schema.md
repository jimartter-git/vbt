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
  within one recording are meaningful. Vitruve alignment is done by rep index,
  not by clock (see `calibration-protocol.md`).
- CSV is chosen for PoC volumes (a 45-min session at 200 Hz ≈ 540k rows ≈ tens
  of MB) because it is trivially `pandas.read_csv`-able and human-eyeballable.
  A length-prefixed binary format is the documented upgrade path once the
  signal is proven; `VBTCore` will own both encoders behind one type.

## Session envelope

Each recorded set produces one CSV file plus a small JSON sidecar of metadata:

```json
{
  "schemaVersion": 1,
  "sessionId": "UUID",
  "startedAt": "ISO-8601 wall clock (phone, for human reference only)",
  "exercise": "deadlift",
  "sampleRateHintHz": 200,
  "deviceModel": "Watch6,18",
  "watchOSVersion": "10.x",
  "sampleCount": 12345,
  "notes": "optional free text (load, set #, RPE)"
}
```

Filename convention: `<sessionId>.csv` and `<sessionId>.json`.

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
  velocityLossPct: Double     // (first-rep MV − last/min MV) / first-rep MV
}
```
