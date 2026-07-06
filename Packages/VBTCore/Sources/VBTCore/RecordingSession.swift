import Foundation

/// What kind of file this metadata sidecar describes.
public enum RecordingKind: String, Codable, Sendable {
    /// A single velocity set inside a workout — one CSV of IMU samples,
    /// filename `<YYYYMMDD>-<LIFT>-<N>_watch`.
    case velocitySet
    /// The workout-wide HR stream that spans one or more velocity sets.
    /// Filename `<YYYYMMDD>-workout_hr[-N]`.
    case workoutHR
}

/// Metadata sidecar for one recorded file (`<stem>.json`).
///
/// One workout produces:
/// - Exactly one `workoutHR` sidecar (the outer HR stream).
/// - Zero or more `velocitySet` sidecars (one per tagged set).
///
/// All sidecars from the same workout carry the same `workoutId`, so an
/// analysis tool can group a workout's HR file with its per-set IMU files
/// without touching HealthKit.
public struct RecordingMetadata: Codable, Equatable, Sendable {
    // v3: introduced two-tier record model. `workoutId` groups files from one
    //     workout; `kind` distinguishes IMU sets from the HR stream;
    //     `stoppedAt` closes each set's time window (for HR slicing);
    //     `setMetadata` carries the user's tags.
    // v2: added `clockAnchorUptimeSeconds` and a datetime fileStem.
    public static let currentSchemaVersion = 3

    public var schemaVersion: Int
    public var sessionId: UUID
    /// Groups sidecars produced during the same outer workout — nil in a
    /// legacy v2 sidecar (there was no outer workout concept).
    public var workoutId: UUID?
    public var kind: RecordingKind

    /// Wall-clock UTC at record START (the human anchor).
    public var startedAt: Date
    /// Wall-clock UTC at record STOP. Closes the window used by HR slicing.
    /// Nil on a still-running / crash-terminated file.
    public var stoppedAt: Date?
    /// Device uptime at the same instant as `startedAt` — see the doc-comment
    /// on the original v2 field for how it maps sample `t` back to UTC.
    public var clockAnchorUptimeSeconds: Double

    /// Free-text lift name kept for BACK-COMPAT with v2 loaders. On a v3
    /// `.velocitySet` sidecar we mirror `setMetadata.lift.rawValue` here so
    /// existing Python / phone-side code that reads `exercise` keeps working
    /// unchanged.
    public var exercise: String
    /// Rich per-set tags (lift + set index + optional mount/RPE/plates/notes).
    /// Nil on a `.workoutHR` sidecar or a legacy v2 file.
    public var setMetadata: SetMetadata?

    public var sampleRateHintHz: Int
    public var deviceModel: String
    public var osVersion: String
    public var sampleCount: Int
    public var notes: String?

    public init(
        sessionId: UUID = UUID(),
        workoutId: UUID? = nil,
        kind: RecordingKind = .velocitySet,
        startedAt: Date = Date(),
        stoppedAt: Date? = nil,
        clockAnchorUptimeSeconds: Double = 0,
        exercise: String = "deadlift",
        setMetadata: SetMetadata? = nil,
        sampleRateHintHz: Int = 200,
        deviceModel: String = "",
        osVersion: String = "",
        sampleCount: Int = 0,
        notes: String? = nil
    ) {
        self.schemaVersion = Self.currentSchemaVersion
        self.sessionId = sessionId
        self.workoutId = workoutId
        self.kind = kind
        self.startedAt = startedAt
        self.stoppedAt = stoppedAt
        self.clockAnchorUptimeSeconds = clockAnchorUptimeSeconds
        self.exercise = exercise
        self.setMetadata = setMetadata
        self.sampleRateHintHz = sampleRateHintHz
        self.deviceModel = deviceModel
        self.osVersion = osVersion
        self.sampleCount = sampleCount
        self.notes = notes
    }

    /// v2 fallback filename (legacy sortable stem): kept for the `.workoutHR`
    /// kind and for any recording without a `setMetadata` tag.
    private static let legacyStampFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd_HHmmss"
        return f
    }()

    /// Base filename (without extension). For a `.velocitySet` file with
    /// `setMetadata`, matches the dataset convention `<YYYYMMDD>-<CODE>-<N>_watch`.
    /// For a `.workoutHR` file, matches `<YYYYMMDD>-workout_hr`. Anything else
    /// falls back to the legacy v2 stem (used by tests and unclassified files).
    public var fileStem: String {
        switch kind {
        case .velocitySet:
            if let set = setMetadata {
                return set.velocitySetFileStem(on: startedAt)
            }
            return legacyStem
        case .workoutHR:
            return workoutHRFileStem(on: startedAt)
        }
    }

    private var legacyStem: String {
        let stamp = Self.legacyStampFormatter.string(from: startedAt)
        let short = sessionId.uuidString.prefix(8)
        let safeExercise = exercise.replacingOccurrences(of: " ", with: "-")
        return "VBT_\(stamp)Z_\(safeExercise)_\(short)"
    }
}
