# Architecture

## Status: PoC / thin vertical slice

Right now this repo proves one thing: **does wrist-IMU velocity survive off the
watch well enough to be useful, validated against a Vitruve?** Everything here
is scoped to that question. The full multi-source platform below is documented
intent, not yet built.

## Target abstraction: `VelocitySource`

The product is multimodal — phone video, BLE VBT devices (Vitruve, Stance,
SmartBarbell-style), and the watch IMU. The bet is that all of them emit the
**same shape** into a common rep + fatigue model:

```
(rep boundaries, velocity profile, range of motion)
```

So `VBTCore` defines a `VelocitySource` protocol from day one (currently a
documented stub). The watch IMU is the first concrete implementation; BLE and
video slot in behind the same protocol later, and a fusion layer combines them
when more than one source is present.

```
┌────────────┐   ┌────────────┐   ┌────────────┐
│ Watch IMU  │   │ BLE device │   │   Video    │   ← VelocitySource impls
└─────┬──────┘   └─────┬──────┘   └─────┬──────┘
      └────────────────┼────────────────┘
                       ▼
              ┌──────────────────┐
              │  Fusion / select │
              └────────┬─────────┘
                       ▼
        ┌──────────────────────────────┐
        │  Rep + Fatigue model          │
        │  • per-rep velocity / ROM     │
        │  • intra-set velocity LOSS    │  ← the differentiated signal
        │  • muscular strain / recovery │
        └──────────────────────────────┘
```

### Why velocity *loss* is the point

HR-based platforms (Whoop, Athlytic) are structurally blind to resistance
training: you can fully fatigue muscle/CNS under heavy load without sustained HR
elevation. Counting every rep and tracking **intra-set velocity loss** — a
well-validated proximity-to-failure / fatigue proxy — produces a *muscular*
strain score those platforms can't compute. Absolute velocity is nice; the
velocity-loss *curve* is the moat.

## Watch capture path (the slice)

```
HKWorkoutSession (keeps sensors alive, blocks sleep)
        │
        ▼
CMBatchedSensorManager.startDeviceMotionUpdates  (~200 Hz batches)
        │  userAcceleration + gravity + attitude
        ▼
Ring buffer ──► CSV file (VBTCore schema) ──► WCSession.transferFile ──► iPhone
```

iPhone is a thin relay: receive file → Documents → expose via share sheet so
raw data reaches a Mac for offline Python analysis.

## Estimation pipeline (offline, Python today → VBTCore later)

1. **Vertical projection** — project `userAcceleration` onto the gravity axis to
   get scalar vertical accel (m/s²). Robust to wrist orientation drift.
2. **Rep detection** — find turnaround points (the ZVU anchors).
3. **ZUPT integration** — integrate accel → velocity *per segment*, anchoring
   velocity ≈ 0 at each turnaround. This kills integration drift, the enemy of
   single-integration velocity. **Per-rep boundary detection is therefore
   foundational, not optional.**
4. **Per-rep metrics** — mean/peak concentric velocity, ROM estimate.

The proven Python algorithm gets ported into `VBTCore` so the *same* code runs
on-device. That port is deliberately deferred until calibration confirms signal.

## Known accuracy caveats (the wrist is not the barbell)

- **Exercise-dependent.** Deadlift & bench (wrist tracks bar) = best; squat (bar
  on back, arm noise) = hard; DB/overhead = decent. We start with **deadlift**.
- **ROM is harder than velocity** — double integration compounds drift. Prefer
  limb-segment length × attitude angles over raw double-integrated displacement.
- **100 Hz is the integration substrate** — `CMBatchedSensorManager` gives the
  headroom (up to 200 Hz device motion) and only delivers inside a workout
  session, which is exactly why the `HKWorkoutSession` is mandatory.

## Repo layout

```
vbt/
├── project.yml            XcodeGen spec (iOS + watchOS + test target)
├── Config/                .xcconfig build settings (shared + per target)
├── Packages/VBTCore/      local Swift Package: shared schema + VelocitySource
├── iOS/                   thin companion: receive + persist + share
├── Watch/                 HKWorkoutSession + high-rate motion capture + transfer
├── analysis/              Python: rep detection, ZUPT velocity, Vitruve compare
└── docs/                  this doc, data-schema.md, calibration-protocol.md
```
