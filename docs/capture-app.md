# Capture app — the phone-as-hub recording rig (design)

> **Status: design note (2026-06-18).** Target architecture for collapsing the current
> multi-device, multi-export capture dance into one iPhone app. No Swift written yet; this
> records the decisions, the constraints (esp. the watchOS one), and the build phases so the
> implementation has a spec. Counterpart docs: `docs/data-schema.md` (the recording
> contract), `docs/sources-and-fusion.md` (why multi-source), `docs/video-storage.md` (R2),
> `docs/watch-imu.md` (the watch signal), CLAUDE.md learning #23 (cross-source time-sync).

## Why

Today a single set is a three-device, hands-on choreography with three separate exports:

| | Device | Start | Stop | Export |
|---|---|---|---|---|
| Ground truth | Vitruve on **iPad** | connect / auto | auto-ends | CSV → Files, manual |
| Video | **iPhone** (stock camera, tripod) | manual | manual | trim → upload to R2, manual |
| Watch IMU | **Apple Watch** (standalone app) | manual on watch | manual on watch | open phone app → export |

Three start taps, three stop taps, three post-hoc exports per set. The fix: make **our
iPhone app the capture hub** so one Bluetooth clicker drives video + watch + AirPods together,
and the app trims + uploads itself. Vitruve stays independent (third-party, can't be driven).

## The target flow

> - Vitruve on the iPad — its own auto/one-tap, **unchanged**.
> - Wearing watch + AirPods Pro 3; iPhone on the tripod; vbt app open.
> - **One tap on the watch to ARM it** at the start of the whole workout (see the asterisk).
> - Then the **clicker starts/stops video + watch + AirPods together, every set**.
> - Afterward the app has all three streams; it trims and uploads — no manual export juggle.

The only per-session manual watch interaction is a single arm tap at the very beginning.

## What each signal is, and where it's captured

The iPhone is the hub. Three of the four sources land on (or relay to) it; Vitruve is parallel.

| Source | API / path | Device that captures | Rate | Clock |
|---|---|---|---|---|
| **Video** | `AVCaptureSession` → `AVAssetWriter`, 1080p/4K **60 fps, HEVC, NO audio** | iPhone (our app) | 60 fps | iPhone |
| **AirPods head IMU** | `CMHeadphoneMotionManager` (iOS/iPadOS/macOS only — **not watchOS**) | iPhone (our app) | ~25 Hz | iPhone |
| **AirPods HR** (Pro 3) | HealthKit (PPG; **HR only, no HRV** as of now) | iPhone via HealthKit | ~1 Hz | UTC |
| **Watch IMU (+ HR)** | `CMBatchedSensorManager` on the watch → `WCSession` file transfer | **Watch**, relayed to phone | ~200 Hz | watch uptime |
| Vitruve (GT) | iPad app, BLE bar device | iPad (parallel) | device | its own |

**No audio anywhere.** We never configure an `AVAudioSession` or touch the AirPods mic —
which removes the one real integration risk (the camera grabbing the AirPods mic would flip
the route to call-mode and disturb head-motion delivery). Video-only + motion-only coexist
cleanly.

**HR comes from the wrist, not the ear, for this rig.** The watch already runs an
`HKWorkoutSession` that samples HR; since the lifter wears the watch, AirPods HR (Pro 3) is
redundant here and only matters for a future **watch-less** config (iPhone + AirPods alone).
The schema/plumbing should treat HR as source-tagged so either can feed it.

## Architecture: the phone is the hub

```
 Apple Watch ──(wrist IMU 200 Hz + HR, standalone record)──► WCSession file ─┐
                                                                              ▼
 AirPods Pro 3 ─(head IMU ~25 Hz, CMHeadphoneMotionManager)─────────────► iPhone app
               ─(HR via HealthKit)─────────────────────────────────────► (the hub)
 Tripod camera ─(HD60 video, AVCaptureSession)──────────────────────────►   │
                                                                            │ trims +
 BT clicker ───(volume-button HID → AVCaptureEventInteraction)──────────►   │ uploads
                                                                            ▼
                                                              R2 (manifest.csv + masters)
 iPad: Vitruve ─────────(independent BLE ground truth)──────────────────────  (parallel)
```

We already have: the iOS app skeleton (`iOS/`), the `WCSession` relay that receives + persists
watch files (`iOS/Services/PhoneConnectivity.swift`), the shared schema (`Packages/VBTCore`),
the cross-device time-sync method (#23), and the R2 bucket + manifest conventions
(`docs/video-storage.md`). New work is the camera, the AirPods capture, the clicker handler,
the unified "set" controller, and in-app trim/upload.

### Time synchronization (the genuinely hard part — mostly already solved)

Three clocks, but the alignment is tractable:

- **Video + AirPods share the iPhone clock** → aligned for free (same device, same mach time).
- **AirPods HR** is UTC via HealthKit → anchor directly.
- **Watch is the outlier** (separate device, uptime clock) — solved already: the session
  envelope's `(startedAt, clockAnchorUptimeSeconds)` pair gives coarse UTC, then **velocity
  cross-correlation** refines the sub-second offset (`analysis/scripts/_align_matrix.py`,
  learning #23 — the 06-15 rows aligned at ~+2 s lag, r up to 0.97).

The unified controller captures one **UTC anchor at set start** and stamps every stream's
session id with it, so post-hoc fusion has a common reference before the cross-corr refine.

## The clicker

Cheap tripod clickers pair as a Bluetooth HID device and emit a **volume-button press** — the
stock Camera app maps volume→shutter, which is why it "just works" there. A custom
`AVCaptureSession` app gets nothing for free.

- **Sanctioned API: `AVCaptureEventInteraction` (iOS 17.2+)** — intercepts the hardware volume
  buttons (volume-down = primary, volume-up = secondary) as capture triggers; ~20 lines,
  App-Store-safe. Also handles the iPhone Camera Control / Action button **and AirPods stem
  clicks** (a zero-extra-hardware trigger fallback).
- **Build-time unknown:** what *this* clicker emits. ~95 % send a volume key (handled
  directly). A few send a media key or an HID keyboard character (e.g. Return) → fallback to
  `UIKeyCommand` / `pressesBegan`. A 5-minute on-device check (pair it, log the event) settles
  which handler; build both paths if it's ambiguous.

## ⚑ The watchOS constraint (shapes the UX — not engineerable away)

**The iPhone cannot reliably cold-launch a fully-closed watch app.** watchOS does not allow
arbitrary background launching of a watch app from the paired phone. So "the clicker starts
the watch data from a closed watch app" is **not** achievable.

What **is** achievable: a watch app running an `HKWorkoutSession` stays alive in the
background and **reachable for live `WCSession` messaging** even with the screen down. So:

1. **One tap on the watch arms it** at the start of the workout (begins the session). Only
   manual watch touch.
2. Backgrounded but alive, it takes **clicker-driven start/stop markers** from the phone
   (`WCSession.sendMessage`) for every set thereafter.

Fallback needing **zero** watch taps: let the watch record the whole workout continuously and
recover per-set boundaries afterward via the #23 velocity cross-correlation. The "arm once,
then clicker-driven" model is the better default (clean per-set files, tight sync); the
continuous model is the resilient backstop.

**Build-time verification (no Xcode in the analysis container — author + flag):** confirm
`WCSession` reachability holds with the watch backgrounded mid-workout (expected per the
workout-session lifetime), and the phone→watch start/stop round-trip latency is small enough
to mark set boundaries usefully (sync is refined post-hoc anyway, so this is for tidiness).

## Build phases (each independently useful)

1. **In-app HD60 camera + unified set controller + clicker.** `AVCaptureSession` (1080p/4K60,
   HEVC, no audio) + `AVCaptureEventInteraction`; capture the UTC anchor; tie a `setId` across
   streams; reuse the existing watch `WCSession` relay. Replaces the stock camera; gives
   phone-clock-synced video. *The bulk of the work — Medium.*
2. **AirPods head-motion capture** (`CMHeadphoneMotionManager`) + **HealthKit HR read**. Small
   code; validate AirPods-motion delivery alongside the running capture session on hardware.
   *Low.*
3. **Phone→watch arm/start/stop** over `WCSession` (the "arm once, clicker-driven" model), so
   the clicker drives the watch too. *Low–Medium.*
4. **In-app trim + direct R2 upload** (multipart PUT, append a `manifest.csv` row). Removes the
   manual trim/Files/upload step entirely. *Medium.*

## Scope / non-goals

- **Vitruve is not integrated** — third-party on the iPad, can't be driven; it stays parallel
  as the BLE ground-truth reference (its own auto/one-tap, unchanged).
- **HRV** is not available from AirPods Pro 3 (HR samples only); recovery-readiness HRV still
  comes from the watch.
- **No audio capture** by design.
- The full multi-set **thermal/battery endurance** of camera-60fps + sensors + relay is still
  unproven (the watch endurance gate is already flagged) — validate on a real multi-set
  session before trusting it for a long workout.

## Open questions to settle on hardware

- The clicker's actual HID event (volume vs. keyboard key) → which handler.
- `CMHeadphoneMotionManager` delivery while an `AVCaptureSession` runs (expected fine with no
  audio; confirm).
- `WCSession` reachability + latency with the watch backgrounded in a workout.
- 4K60 vs 1080p60 for the masters (R2 cost vs CV benefit — `docs/video-storage.md` already
  notes native 4K is impractical to flow; a 1080p60 master may be the sweet spot).
</content>
