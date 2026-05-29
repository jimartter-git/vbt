# VBT — velocity-based training & muscular-fatigue tracking

A multimodal platform that estimates rep velocity, range of motion, and per-rep
fatigue from multiple sources — phone video, BLE VBT devices, and (the bet) a
consumer smartwatch's onboard IMU. The thesis: HR-based platforms are
structurally blind to resistance training; by counting every rep and tracking
intra-set **velocity loss** (a validated proximity-to-failure proxy), VBT builds
a *muscular* strain & recovery score they can't.

> **Status: PoC / thin vertical slice.** Goal right now is to prove the wrist
> signal survives off the watch and calibrate it against a Vitruve — not to ship
> UI. See [`docs/architecture.md`](docs/architecture.md).

## What's here

```
vbt/
├── project.yml            XcodeGen spec (iOS + watchOS, embeds watch app)
├── Config/                .xcconfig build settings (shared + per target)
├── Packages/VBTCore/      shared Swift package: MotionSample schema, CSV
│                          contract, VelocitySource protocol (the abstraction)
├── Watch/                 watchOS: HKWorkoutSession + CMBatchedSensorManager
│                          high-rate capture → CSV → transfer to phone
├── iOS/                   thin companion: receive + persist + share recordings
├── analysis/              Python: rep detection, ZUPT velocity, Vitruve compare
└── docs/                  architecture, data schema, calibration protocol
```

## Build the apps (on a Mac)

This repo has **no committed `.xcodeproj`** — it's generated from `project.yml`.

```bash
brew install xcodegen          # once
xcodegen generate              # regenerate after adding/moving/removing files
open VBT.xcodeproj
```

Run the `VBTWatch` scheme on a paired Apple Watch (Series 8 / SE2 / Ultra+ for
true ~200 Hz). Tap **Start**, do a set of deadlifts, tap **Stop** — the watch
records device motion and transfers a CSV to the phone. Open the `VBTPhone` app,
share the CSV to your Mac, and analyze it (below).

### First-build checklist (couldn't be validated off-Mac)

This scaffold was authored on Linux without Xcode, so verify on first open:

1. **Signing** — set `DEVELOPMENT_TEAM` (in Xcode, or a local `.xcconfig`
   override). Enable the **HealthKit** capability on the `VBTWatch` target so
   provisioning matches `Watch/Resources/VBTWatch.entitlements`.
2. **`CMBatchedSensorManager` API** — confirm the
   `startDeviceMotionUpdates(handler:)` signature against your installed
   watchOS 10 SDK (`Watch/Services/MotionRecorder.swift`). A `CMMotionManager`
   ~100 Hz fallback is wired in behind a capability check.
3. **Watch embedding** — confirm XcodeGen's `embed: true` produced the watch
   app inside the iOS app (paired-companion layout). Bundle ids are
   `com.vbt.app` / `com.vbt.app.watchkitapp`.
4. Watch the live **Hz readout** on the watch during a set — it should sit near
   200 Hz. If it sags, that's the throttling risk we're de-risking first.

## Analysis pipeline (Python)

```bash
cd analysis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                                   # validates the ZUPT math
python scripts/analyze_session.py --demo    # synthetic 5-rep demo
python scripts/analyze_session.py data/<sessionId>.csv --out session.png
```

See [`analysis/README.md`](analysis/README.md) and
[`docs/calibration-protocol.md`](docs/calibration-protocol.md) for the
watch-vs-Vitruve calibration workflow.

## The riskiest assumption (de-risk first)

Can watchOS sustain ~200 Hz device motion through a full multi-set session
without throttling, sleep, or battery/thermal death — and get the data off
intact? The watch app's live rate readout + the transfer path exist to answer
exactly that before any further architecture investment.
