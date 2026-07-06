import Foundation
import HealthKit
import VBTCore

/// Streams heart-rate samples during the outer workout into an in-memory
/// buffer, so we can write a workout-wide `<YYYYMMDD>-workout_hr.csv` sidecar
/// that Python analysis can slice by any velocity set's `[startedAt, stoppedAt]`
/// window (HRR30/60/90, peak-in-set, session TRIMP). See `docs/data-schema.md`.
///
/// HR is also flowing into the `HKLiveWorkoutBuilder`'s attached HR samples
/// under the covers — this recorder is the redundant, portable copy that
/// doesn't require an HK export on the Mac.
@MainActor
final class HeartRateRecorder: ObservableObject {

    /// The live BPM reading (published for the workout screen).
    @Published private(set) var latestBpm: Double = 0
    @Published private(set) var sampleCount: Int = 0

    private let healthStore = HKHealthStore()
    private var query: HKAnchoredObjectQuery?
    private var anchor: HKQueryAnchor?

    /// Clock anchor — set at `start()`, mirrored into the sidecar. Consumers
    /// use `sampleT = (utc − startedAt) + clockAnchorUptimeSeconds` to align
    /// HR samples with IMU samples on the same boot clock.
    private(set) var startWallClock: Date?
    private(set) var startUptimeSeconds: Double?

    private(set) var samples: [HeartRateSample] = []

    private let heartRateUnit = HKUnit.count().unitDivided(by: .minute())

    func start() {
        samples.removeAll(keepingCapacity: true)
        sampleCount = 0
        latestBpm = 0
        anchor = nil
        startUptimeSeconds = ProcessInfo.processInfo.systemUptime
        startWallClock = Date()

        let type = HKQuantityType(.heartRate)
        // Anchored query streams HR samples as HealthKit records them (~1 Hz
        // during an active workout). The initial-results handler carries
        // anything already stored since `startWallClock`; the update handler
        // streams the rest live.
        let query = HKAnchoredObjectQuery(
            type: type,
            predicate: HKQuery.predicateForSamples(withStart: startWallClock, end: nil, options: .strictStartDate),
            anchor: nil,
            limit: HKObjectQueryNoLimit
        ) { _, samples, _, newAnchor, _ in
            Task { @MainActor [weak self] in
                self?.ingest(samples: samples, newAnchor: newAnchor)
            }
        }
        query.updateHandler = { _, samples, _, newAnchor, _ in
            Task { @MainActor [weak self] in
                self?.ingest(samples: samples, newAnchor: newAnchor)
            }
        }
        self.query = query
        healthStore.execute(query)
    }

    func stop() {
        if let query { healthStore.stop(query) }
        query = nil
    }

    private func ingest(samples raw: [HKSample]?, newAnchor: HKQueryAnchor?) {
        anchor = newAnchor
        guard let raw = raw as? [HKQuantitySample], !raw.isEmpty else { return }
        let anchorUptime = startUptimeSeconds ?? 0
        let anchorWall = startWallClock ?? Date()
        for s in raw {
            let bpm = s.quantity.doubleValue(for: heartRateUnit)
            // Approximate uptime by projecting wall-clock offset onto the
            // uptime axis (both share the boot clock during a session).
            let dt = s.startDate.timeIntervalSince(anchorWall)
            let t = anchorUptime + dt
            samples.append(HeartRateSample(t: t, utc: s.startDate, bpm: bpm))
            latestBpm = bpm
        }
        sampleCount = samples.count
    }
}
