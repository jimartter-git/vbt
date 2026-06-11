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
///
/// `confidence` (0…1) is what makes graceful degradation and fusion possible —
/// see docs/sources-and-fusion.md. It is carried from day one precisely because
/// retrofitting a confidence dimension after call sites exist is the painful
/// kind of change.
public struct RepMetrics: Codable, Equatable, Sendable {
    public var repIndex: Int
    public var startTime: Double          // s, relative to recording
    public var turnaroundTime: Double     // s, the ZVU anchor
    public var endTime: Double            // s
    public var meanConcentricVelocity: Double  // m/s
    public var peakConcentricVelocity: Double  // m/s
    public var rangeOfMotion: Double           // m
    /// How much to trust this rep, 0…1. Drives fusion weighting and the
    /// "tap to verify" / active-learning UX.
    public var confidence: Double
    /// True when absolute velocity is not calibrated for this lift/source and
    /// only relative/trend values should be trusted (e.g. cable, watch-only).
    public var velocityIsRelativeOnly: Bool

    public init(
        repIndex: Int, startTime: Double, turnaroundTime: Double, endTime: Double,
        meanConcentricVelocity: Double, peakConcentricVelocity: Double, rangeOfMotion: Double,
        confidence: Double = 1.0,
        velocityIsRelativeOnly: Bool = false
    ) {
        self.repIndex = repIndex
        self.startTime = startTime
        self.turnaroundTime = turnaroundTime
        self.endTime = endTime
        self.meanConcentricVelocity = meanConcentricVelocity
        self.peakConcentricVelocity = peakConcentricVelocity
        self.rangeOfMotion = rangeOfMotion
        self.confidence = confidence
        self.velocityIsRelativeOnly = velocityIsRelativeOnly
    }
}

/// Quality summary for one source's contribution to a set — the input to
/// confidence-weighted fusion (docs/sources-and-fusion.md).
public struct SourceQuality: Codable, Equatable, Sendable {
    /// Fraction of the set where the source had usable signal (1 = no dropouts).
    public var coverage: Double
    /// Mean per-rep confidence this source produced.
    public var meanConfidence: Double
    /// Optional human-readable note (e.g. "tracking lost mid-set").
    public var note: String?

    public init(coverage: Double = 1.0, meanConfidence: Double = 1.0, note: String? = nil) {
        self.coverage = coverage
        self.meanConfidence = meanConfidence
        self.note = note
    }
}

/// Summary of one set, source-agnostic. Carries which source produced it and an
/// aggregate confidence so the fusion layer can weight and reconcile multiple
/// summaries for the same set.
public struct SetSummary: Codable, Equatable, Sendable {
    public var reps: [RepMetrics]
    /// Intra-set velocity loss (%) — the validated proximity-to-failure proxy.
    public var velocityLossPct: Double
    /// Which source produced this summary (nil for a fused result).
    public var sourceID: String?
    /// Aggregate confidence for the set (mean of rep confidence by default).
    public var confidence: Double

    public init(reps: [RepMetrics], sourceID: String? = nil, confidence: Double? = nil) {
        self.reps = reps
        self.sourceID = sourceID

        // THE canonical velocity-loss definition — keep in lock-step with
        // `analysis/vbt_analysis/metrics.py` (velocity_loss_pct) and docs/data-schema.md:
        // loss = (best − terminal) / best, where terminal = mean of the LAST
        // min(2, n−1) reps. Never best→min (a mid-set slow rep must not inflate
        // loss past the set's end); a 2-rep terminal window absorbs single
        // terminal-rep noise (the least reliably measured rep in the set).
        // Sets with fewer than 3 reps are too short to score → 0.
        let mvs = reps.map(\.meanConcentricVelocity)
        if mvs.count >= 3, let best = mvs.max(), best > 0 {
            let k = min(2, mvs.count - 1)
            let terminal = mvs.suffix(k).reduce(0, +) / Double(k)
            self.velocityLossPct = (best - terminal) / best * 100.0
        } else {
            self.velocityLossPct = 0
        }

        if let confidence {
            self.confidence = confidence
        } else if reps.isEmpty {
            self.confidence = 0
        } else {
            self.confidence = reps.map(\.confidence).reduce(0, +) / Double(reps.count)
        }
    }
}

/// Any sensor/algorithm that can turn a recording into per-set rep metrics.
/// Watch IMU is the first implementer; BLE, video, and AirPods IMU conform
/// later, each reporting its own `SourceQuality` so fusion can weight them.
public protocol VelocitySource {
    /// Stable identifier for the source kind (e.g. "watchIMU", "vitruveBLE").
    var sourceID: String { get }

    /// Produce a set summary from raw motion samples for the given exercise.
    func estimate(from samples: [MotionSample], exercise: String) throws -> SetSummary
}
