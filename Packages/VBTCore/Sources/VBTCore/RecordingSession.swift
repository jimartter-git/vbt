import Foundation

/// Metadata sidecar for one recorded set (serialized to `<sessionId>.json`).
/// Mirrors the "Session envelope" in `docs/data-schema.md`.
public struct RecordingMetadata: Codable, Equatable, Sendable {
    // v2: added `clockAnchorUptimeSeconds` (uptime→UTC anchor) and a datetime fileStem.
    public static let currentSchemaVersion = 2

    public var schemaVersion: Int
    public var sessionId: UUID
    /// Wall-clock UTC at the moment recording started — the human-readable anchor
    /// (drives `fileStem`) and the wall-clock half of the uptime→UTC mapping.
    public var startedAt: Date
    /// Device uptime (`ProcessInfo.systemUptime`, seconds since boot) captured at the
    /// SAME instant as `startedAt`. Samples carry `t = CMDeviceMotion.timestamp`, which
    /// is the same boot clock, so a consumer recovers absolute UTC per sample:
    ///   `sampleUTC = startedAt + (sample.t − clockAnchorUptimeSeconds)`.
    /// (CMDeviceMotion.timestamp is uptime, NOT wall clock — this pair is the only
    /// thing that makes a recording cross-device / cross-source time-alignable.)
    public var clockAnchorUptimeSeconds: Double
    public var exercise: String
    public var sampleRateHintHz: Int
    public var deviceModel: String
    public var osVersion: String
    public var sampleCount: Int
    public var notes: String?

    public init(
        sessionId: UUID = UUID(),
        startedAt: Date = Date(),
        clockAnchorUptimeSeconds: Double = 0,
        exercise: String = "deadlift",
        sampleRateHintHz: Int = 200,
        deviceModel: String = "",
        osVersion: String = "",
        sampleCount: Int = 0,
        notes: String? = nil
    ) {
        self.schemaVersion = Self.currentSchemaVersion
        self.sessionId = sessionId
        self.startedAt = startedAt
        self.clockAnchorUptimeSeconds = clockAnchorUptimeSeconds
        self.exercise = exercise
        self.sampleRateHintHz = sampleRateHintHz
        self.deviceModel = deviceModel
        self.osVersion = osVersion
        self.sampleCount = sampleCount
        self.notes = notes
    }

    /// UTC, compact, filename-safe timestamp formatter (`yyyy-MM-dd_HHmmss`).
    private static let stampFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd_HHmmss"
        return f
    }()

    /// Base filename (without extension) for this session's CSV/JSON pair.
    /// Human-readable + SORTABLE: start time (UTC) → exercise → short id, e.g.
    /// `VBT_2026-06-15_182203Z_deadlift_CE3E8765`. Replaces the bare UUID so the
    /// phone's session list is legible and orderable (the lifter mis-ordered the
    /// 06-15 rows because every file was an indistinguishable UUID).
    public var fileStem: String {
        let stamp = Self.stampFormatter.string(from: startedAt)
        let short = sessionId.uuidString.prefix(8)
        let safeExercise = exercise.replacingOccurrences(of: " ", with: "-")
        return "VBT_\(stamp)Z_\(safeExercise)_\(short)"
    }
}
