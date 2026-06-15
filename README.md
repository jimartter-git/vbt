# VBT — velocity-based training & muscular-fatigue tracking

A multimodal platform that estimates rep velocity, range of motion, and per-rep
fatigue from multiple sources — phone video, BLE VBT devices, and (the bet) a
consumer smartwatch's onboard IMU. The thesis: HR-based platforms are
structurally blind to resistance training; by counting every rep and tracking
intra-set **velocity loss** (a validated proximity-to-failure proxy), VBT builds
a *muscular* strain & recovery score they can't.

> **Status: PoC / thin vertical slice — capture path device-validated
> (2026-06-15, Apple Watch Ultra).** The wrist signal provably survives off the
> watch at ~200 Hz; next is calibrating *the number* against a Vitruve — not to
> ship UI. See [`docs/architecture.md`](docs/architecture.md).
>
> The full multi-source vision — AirPods + video + BLE fusion, a learned
> per-user rep-shape prior, any-lift support, graceful degradation to
> watch-only, and a manual rep editor that trains the model — lives in
> [`docs/sources-and-fusion.md`](docs/sources-and-fusion.md), with a bite-sized
> phase plan at the end.

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

### First-build checklist — ✅ VALIDATED on hardware (2026-06-15, Apple Watch Ultra, watchOS 26.5)

This scaffold was authored on Linux without Xcode; the first real-device build
confirmed every item below worked **unmodified**. Kept here as the setup guide:

1. **Signing** — set `DEVELOPMENT_TEAM` (in Xcode, or a local `.xcconfig`
   override). Enable the **HealthKit** capability on the `VBTWatch` target so
   provisioning matches `Watch/Resources/VBTWatch.entitlements`. ✅ built + signed.
2. **`CMBatchedSensorManager` API** — the `startDeviceMotionUpdates(handler:)`
   signature in `Watch/Services/MotionRecorder.swift` compiled and ran as
   authored on the watchOS 26 SDK. A `CMMotionManager` ~100 Hz fallback is wired
   in behind a capability check (not needed on the Ultra). ✅
3. **Watch embedding** — XcodeGen's `embed: true` produced the watch app inside
   the iOS app (paired-companion layout); running `VBTPhone` installed the watch
   app on the paired Ultra. Bundle ids `com.vbt.app` / `com.vbt.app.watchkitapp`. ✅
4. **Live Hz readout** — sat near the **200 Hz** target continuously through a
   set (5,317 samples ≈ 27 s), no sag → **no throttling on the first set.** ✅

> First-device-bringup gotchas (new Mac): a development cert whose private key
> lives on another machine → **Revoke** and let Xcode mint a fresh one; the watch
> only exposes **Developer Mode** *after* Xcode reaches it (run `VBTPhone` to the
> phone to install the embedded watch app — that triggers it); Xcode talks to the
> watch over **Wi-Fi** (same network as the Mac), not the charging cable; the
> "prepare for development / copy shared cache" step is slow and dies if the watch
> sleeps — keep it awake on the charger.

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

## The riskiest assumption — ✅ first answer is YES (2026-06-15)

Can watchOS sustain ~200 Hz device motion through a session without throttling,
sleep, or battery/thermal death — and get the data off intact? **First real-device
run (Apple Watch Ultra, watchOS 26.5): yes.** `CMBatchedSensorManager` inside an
`HKWorkoutSession` held **~200 Hz continuously to 5,317 samples (~27 s)** and the
CSV transferred to the phone intact. The bet that the wrist signal survives off
the watch is no longer theoretical.

**Still open** (the honest remainder): (1) endurance across a **full multi-set
session** — battery/thermal/throttling over minutes, not one 27 s set; (2) signal
**accuracy** — does the ZUPT velocity track a Vitruve? See
`docs/calibration-protocol.md`. Validating *transport* was step one; validating
*the number* is the active phase.
