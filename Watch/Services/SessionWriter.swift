import Foundation
import WatchKit
import VBTCore

/// Serializes captured samples to CSV + JSON sidecar in a temp directory,
/// ready for `transferFile` to the phone. Two file kinds:
///
/// - `writeVelocitySet` — one per tagged set, filename
///   `<YYYYMMDD>-<LIFT>-<N>_watch.csv` (dataset convention).
/// - `writeWorkoutHR` — one per outer workout, filename
///   `<YYYYMMDD>-workout_hr.csv`.
///
/// Both carry the same `workoutId` in their sidecars so a consumer can group
/// a workout's HR file with its per-set IMU files without touching HealthKit.
enum SessionWriter {

    struct Output {
        let csv: URL
        let json: URL
        let metadata: RecordingMetadata
    }

    // MARK: - Velocity set (IMU)

    static func writeVelocitySet(
        samples: [MotionSample],
        setMetadata: SetMetadata,
        workoutId: UUID,
        rateHint: Int,
        startedAt: Date,
        stoppedAt: Date,
        clockAnchorUptimeSeconds: Double,
        notes: String? = nil
    ) throws -> Output {
        let device = WKInterfaceDevice.current()
        let meta = RecordingMetadata(
            workoutId: workoutId,
            kind: .velocitySet,
            startedAt: startedAt,
            stoppedAt: stoppedAt,
            clockAnchorUptimeSeconds: clockAnchorUptimeSeconds,
            exercise: setMetadata.lift.rawValue,
            setMetadata: setMetadata,
            sampleRateHintHz: rateHint,
            deviceModel: device.model,
            osVersion: device.systemVersion,
            sampleCount: samples.count,
            notes: notes ?? setMetadata.notes
        )
        let csvBody = MotionSampleCSV.encode(samples)
        return try write(csvBody: csvBody, metadata: meta)
    }

    // MARK: - Workout HR

    static func writeWorkoutHR(
        samples: [HeartRateSample],
        workoutId: UUID,
        startedAt: Date,
        stoppedAt: Date,
        clockAnchorUptimeSeconds: Double
    ) throws -> Output {
        let device = WKInterfaceDevice.current()
        let meta = RecordingMetadata(
            workoutId: workoutId,
            kind: .workoutHR,
            startedAt: startedAt,
            stoppedAt: stoppedAt,
            clockAnchorUptimeSeconds: clockAnchorUptimeSeconds,
            exercise: "workout_hr",
            setMetadata: nil,
            sampleRateHintHz: 1,
            deviceModel: device.model,
            osVersion: device.systemVersion,
            sampleCount: samples.count,
            notes: nil
        )
        let csvBody = HeartRateSampleCSV.encode(samples)
        return try write(csvBody: csvBody, metadata: meta)
    }

    // MARK: - Shared

    private static func write(csvBody: String, metadata: RecordingMetadata) throws -> Output {
        let dir = FileManager.default.temporaryDirectory
        let csvURL = dir.appendingPathComponent("\(metadata.fileStem).csv")
        let jsonURL = dir.appendingPathComponent("\(metadata.fileStem).json")

        try Data(csvBody.utf8).write(to: csvURL, options: .atomic)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(metadata).write(to: jsonURL, options: .atomic)

        return Output(csv: csvURL, json: jsonURL, metadata: metadata)
    }
}
