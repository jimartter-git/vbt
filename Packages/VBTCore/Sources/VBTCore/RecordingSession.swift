import Foundation

/// Metadata sidecar for one recorded set (serialized to `<sessionId>.json`).
/// Mirrors the "Session envelope" in `docs/data-schema.md`.
public struct RecordingMetadata: Codable, Equatable, Sendable {
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    public var sessionId: UUID
    public var startedAt: Date
    public var exercise: String
    public var sampleRateHintHz: Int
    public var deviceModel: String
    public var osVersion: String
    public var sampleCount: Int
    public var notes: String?

    public init(
        sessionId: UUID = UUID(),
        startedAt: Date = Date(),
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
        self.exercise = exercise
        self.sampleRateHintHz = sampleRateHintHz
        self.deviceModel = deviceModel
        self.osVersion = osVersion
        self.sampleCount = sampleCount
        self.notes = notes
    }

    /// Base filename (without extension) for this session's CSV/JSON pair.
    public var fileStem: String { sessionId.uuidString }
}
