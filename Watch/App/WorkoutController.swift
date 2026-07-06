import Foundation
import Combine
import VBTCore

/// Owns the two-tier record model on the watch:
/// - **Outer workout** (`HKWorkoutSession` + HR streaming): starts on
///   `startWorkout()`, ends on `endWorkout()` → the `HKWorkout` lands in Apple
///   Health, and the workout-wide HR sidecar (`YYYYMMDD-workout_hr.csv`) is
///   sent to the phone. This is what Athlytic / Whoop / Apple Health ingest.
/// - **Inner velocity sets** (`MotionRecorder` cycles): start/stop N times
///   during a running workout. Each cycle produces one
///   `YYYYMMDD-<LIFT>-<N>_watch.csv` + JSON sidecar sent to the phone.
///
/// The UI drives four transitions:
///   idle → workoutRunning (Start Workout)
///   workoutRunning → setRecording (Tag Set with metadata)
///   setRecording → workoutRunning (Stop Set)
///   workoutRunning → idle (End Workout)
@MainActor
final class WorkoutController: ObservableObject {

    enum Phase: Equatable {
        case idle
        case workoutRunning
        case setRecording(SetMetadata)

        var isWorkoutActive: Bool { self != .idle }
        var isRecordingSet: Bool {
            if case .setRecording = self { return true } else { return false }
        }
    }

    // Live state for the UI.
    @Published private(set) var phase: Phase = .idle
    @Published private(set) var completedSets: [SetMetadata] = []
    @Published private(set) var statusMessage: String = "Ready"

    // Live counters — mirrored from the recorders so views can bind directly.
    @Published private(set) var sampleCount: Int = 0
    @Published private(set) var measuredRateHz: Double = 0
    @Published private(set) var latestBpm: Double = 0

    private let workout = WorkoutManager()
    private let motion = MotionRecorder()
    private let heart = HeartRateRecorder()
    private let connectivity = WatchConnectivityManager.shared
    private let store = SetMetadataStore.shared

    /// One id shared by every file produced during this workout (velocity sets
    /// + HR sidecar). Nil while idle.
    private var currentWorkoutId: UUID?
    private var workoutStartedAt: Date?

    /// Set-scoped clock — used to time-bracket the set for HR slicing.
    private var currentSetStartedAt: Date?

    init() {
        motion.$sampleCount.assign(to: &$sampleCount)
        motion.$measuredRateHz.assign(to: &$measuredRateHz)
        heart.$latestBpm.assign(to: &$latestBpm)
    }

    var targetRateHz: Int { motion.targetRateHz }

    // MARK: - Outer workout

    func startWorkout() {
        Task {
            do {
                try await workout.requestAuthorization()
                try workout.start()
                heart.start()
                currentWorkoutId = UUID()
                workoutStartedAt = Date()
                completedSets = []
                phase = .workoutRunning
                statusMessage = "Workout running"
            } catch {
                statusMessage = "Start failed: \(error.localizedDescription)"
            }
        }
    }

    func endWorkout() {
        // Guard: if a set is somehow still recording, stop it first so its
        // CSV isn't lost.
        if case .setRecording = phase { stopSet() }
        heart.stop()
        workout.stop()
        let workoutStopped = Date()
        statusMessage = "Saving workout…"
        Task { await finalizeWorkoutHR(stoppedAt: workoutStopped) }
    }

    private func finalizeWorkoutHR(stoppedAt: Date) async {
        defer {
            phase = .idle
            currentWorkoutId = nil
            workoutStartedAt = nil
        }
        guard let workoutId = currentWorkoutId,
              let startedAt = workoutStartedAt,
              let anchor = heart.startUptimeSeconds,
              !heart.samples.isEmpty
        else {
            statusMessage = completedSets.isEmpty ? "Workout ended" : "Workout ended (no HR)"
            return
        }
        do {
            let out = try SessionWriter.writeWorkoutHR(
                samples: heart.samples,
                workoutId: workoutId,
                startedAt: startedAt,
                stoppedAt: stoppedAt,
                clockAnchorUptimeSeconds: anchor
            )
            connectivity.sendFile(out.csv, metadata: ["kind": "workout_hr"])
            connectivity.sendFile(out.json, metadata: ["kind": "workout_hr_json"])
            statusMessage = "Workout saved (\(heart.sampleCount) HR)"
        } catch {
            statusMessage = "HR save failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Inner velocity set

    /// The metadata to prefill the tag-set form — sticky defaults with
    /// `setIndex` auto-incremented to the next value for this lift-day.
    func nextSuggestedSetMetadata() -> SetMetadata {
        store.nextSuggestedMetadata()
    }

    /// Called by TagSetView when the user confirms. Begins recording motion
    /// for one set.
    func startSet(with metadata: SetMetadata) {
        guard case .workoutRunning = phase else {
            statusMessage = "Start a workout first"
            return
        }
        store.remember(metadata)
        currentSetStartedAt = Date()
        motion.start()
        phase = .setRecording(metadata)
        statusMessage = "\(metadata.lift.displayName) set \(metadata.setIndex)"
    }

    func stopSet() {
        guard case .setRecording(let metadata) = phase else { return }
        motion.stop()
        let stoppedAt = Date()
        let samples = motion.capturedSamples
        completedSets.append(metadata)
        phase = .workoutRunning
        statusMessage = "Sending \(metadata.lift.displayName) \(metadata.setIndex)…"
        Task { await sendSet(metadata: metadata, samples: samples, stoppedAt: stoppedAt) }
    }

    private func sendSet(
        metadata: SetMetadata,
        samples: [MotionSample],
        stoppedAt: Date
    ) async {
        guard !samples.isEmpty else {
            statusMessage = "\(metadata.lift.displayName) \(metadata.setIndex): no samples"
            return
        }
        guard let workoutId = currentWorkoutId,
              let startedAt = currentSetStartedAt ?? motion.startWallClock,
              let anchor = motion.startUptimeSeconds
        else {
            statusMessage = "Missing workout context"
            return
        }
        do {
            let out = try SessionWriter.writeVelocitySet(
                samples: samples,
                setMetadata: metadata,
                workoutId: workoutId,
                rateHint: motion.targetRateHz,
                startedAt: startedAt,
                stoppedAt: stoppedAt,
                clockAnchorUptimeSeconds: anchor
            )
            connectivity.sendFile(out.csv, metadata: ["kind": "velocity_set", "lift": metadata.lift.rawValue])
            connectivity.sendFile(out.json, metadata: ["kind": "velocity_set_json"])
            statusMessage = "Sent \(metadata.lift.displayName) \(metadata.setIndex) (\(samples.count))"
        } catch {
            statusMessage = "Save failed: \(error.localizedDescription)"
        }
        currentSetStartedAt = nil
    }
}
