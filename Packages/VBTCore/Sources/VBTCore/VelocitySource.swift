import Foundation

// MARK: - The cross-source abstraction (intentional stub for the PoC)
//
// The product is multimodal: watch IMU, BLE VBT devices, and phone video all
// emit the SAME shape — (rep boundaries, velocity profile, ROM) — into a common
// rep + fatigue model. This protocol is defined from day one so those sources
// are interchangeable, but only the watch-IMU path is exercised in the PoC.
// The proven Python estimator (analysis/) gets ported in behind here once
// calibration confirms the signal; see docs/architecture.md.

/// Per-rep derived metrics. Mirrors `RepMetrics` in the Python pipeline and the
/// "Derived metrics" contract in docs/data-schema.md.
public struct RepMetrics: Codable, Equatable, Sendable {
    public var repIndex: Int
    public var startTime: Double          // s, relative to recording
    public var turnaroundTime: Double     // s, the ZVU anchor
    public var endTime: Double            // s
    public var meanConcentricVelocity: Double  // m/s
    public var peakConcentricVelocity: Double  // m/s
    public var rangeOfMotion: Double           // m

    public init(
        repIndex: Int, startTime: Double, turnaroundTime: Double, endTime: Double,
        meanConcentricVelocity: Double, peakConcentricVelocity: Double, rangeOfMotion: Double
    ) {
        self.repIndex = repIndex
        self.startTime = startTime
        self.turnaroundTime = turnaroundTime
        self.endTime = endTime
        self.meanConcentricVelocity = meanConcentricVelocity
        self.peakConcentricVelocity = peakConcentricVelocity
        self.rangeOfMotion = rangeOfMotion
    }
}

/// Summary of one set, source-agnostic.
public struct SetSummary: Codable, Equatable, Sendable {
    public var reps: [RepMetrics]
    /// Intra-set velocity loss (%) — the validated proximity-to-failure proxy.
    public var velocityLossPct: Double

    public init(reps: [RepMetrics]) {
        self.reps = reps
        let mvs = reps.map(\.meanConcentricVelocity)
        if let best = mvs.max(), best > 0, let worst = mvs.min() {
            self.velocityLossPct = (best - worst) / best * 100.0
        } else {
            self.velocityLossPct = 0
        }
    }
}

/// Any sensor/algorithm that can turn a recording into per-set rep metrics.
/// Watch IMU is the first implementer; BLE and video conform later.
public protocol VelocitySource {
    /// Stable identifier for the source kind (e.g. "watchIMU", "vitruveBLE").
    var sourceID: String { get }

    /// Produce a set summary from raw motion samples for the given exercise.
    func estimate(from samples: [MotionSample], exercise: String) throws -> SetSummary
}
