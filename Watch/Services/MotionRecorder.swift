import Foundation
import CoreMotion
import VBTCore

/// High-rate device-motion capture.
///
/// Primary path is `CMBatchedSensorManager` (watchOS 10+, Series 8 / SE2 /
/// Ultra), which delivers batched device motion up to ~200 Hz and is designed
/// to run inside a workout session — exactly our use case. We fall back to
/// `CMMotionManager` at ~100 Hz on hardware/OS without batched support.
///
/// NOTE (verify on first build): confirm the `CMBatchedSensorManager`
/// `startDeviceMotionUpdates(handler:)` signature against the installed
/// watchOS 10 SDK; the batched API is relatively new. The fallback path uses
/// the long-stable `CMMotionManager` API.
@MainActor
final class MotionRecorder: ObservableObject {
    /// Live counters for the UI (so we can confirm the sensor isn't throttled).
    @Published private(set) var sampleCount: Int = 0
    @Published private(set) var measuredRateHz: Double = 0

    private var samples: [MotionSample] = []
    private let motionManager = CMMotionManager()
    private var batchedManager: CMBatchedSensorManager?
    private var usingBatched = false

    private var firstTimestamp: Double?
    private var lastTimestamp: Double?

    /// Clock anchor captured at `start()`: wall-clock UTC + the device-uptime reading
    /// at the same instant. `ProcessInfo.systemUptime` and `CMDeviceMotion.timestamp`
    /// share the boot epoch, so this pair maps every sample's `t` to absolute UTC
    /// downstream (see `RecordingMetadata.clockAnchorUptimeSeconds`).
    private(set) var startWallClock: Date?
    private(set) var startUptimeSeconds: Double?

    var capturedSamples: [MotionSample] { samples }

    var targetRateHz: Int {
        if #available(watchOS 10.0, *), CMBatchedSensorManager.isDeviceMotionSupported {
            return 200
        }
        return 100
    }

    func start() {
        samples.removeAll(keepingCapacity: true)
        sampleCount = 0
        measuredRateHz = 0
        firstTimestamp = nil
        lastTimestamp = nil
        // Capture the wall-clock↔uptime anchor BEFORE updates flow (read back-to-back:
        // both advance on the same boot clock, so the tiny gap between them is harmless).
        startUptimeSeconds = ProcessInfo.processInfo.systemUptime
        startWallClock = Date()

        if #available(watchOS 10.0, *), CMBatchedSensorManager.isDeviceMotionSupported {
            startBatched()
        } else {
            startLegacy()
        }
    }

    func stop() {
        if usingBatched, #available(watchOS 10.0, *) {
            batchedManager?.stopDeviceMotionUpdates()
            batchedManager = nil
        } else {
            motionManager.stopDeviceMotionUpdates()
        }
    }

    // MARK: - Capture paths

    @available(watchOS 10.0, *)
    private func startBatched() {
        usingBatched = true
        let manager = CMBatchedSensorManager()
        batchedManager = manager
        manager.startDeviceMotionUpdates { [weak self] batch, _ in
            guard let self, let batch else { return }
            Task { @MainActor in
                for dm in batch { self.append(dm) }
            }
        }
    }

    private func startLegacy() {
        usingBatched = false
        guard motionManager.isDeviceMotionAvailable else { return }
        motionManager.deviceMotionUpdateInterval = 1.0 / 100.0
        let queue = OperationQueue()
        motionManager.startDeviceMotionUpdates(to: queue) { [weak self] motion, _ in
            guard let self, let motion else { return }
            Task { @MainActor in self.append(motion) }
        }
    }

    // MARK: - Sample handling

    private func append(_ dm: CMDeviceMotion) {
        let q = dm.attitude.quaternion
        samples.append(
            MotionSample(
                t: dm.timestamp,
                uaX: dm.userAcceleration.x, uaY: dm.userAcceleration.y, uaZ: dm.userAcceleration.z,
                gX: dm.gravity.x, gY: dm.gravity.y, gZ: dm.gravity.z,
                qW: q.w, qX: q.x, qY: q.y, qZ: q.z
            )
        )
        sampleCount = samples.count

        if firstTimestamp == nil { firstTimestamp = dm.timestamp }
        lastTimestamp = dm.timestamp
        if let first = firstTimestamp, let last = lastTimestamp, last > first {
            measuredRateHz = Double(samples.count - 1) / (last - first)
        }
    }
}
