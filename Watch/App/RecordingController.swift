import Foundation
import Combine
import VBTCore

/// Orchestrates a recording: HealthKit workout (keeps sensors alive) + motion
/// capture + transfer to phone. Owns the moving pieces and publishes the
/// minimal state the watch UI needs.
@MainActor
final class RecordingController: ObservableObject {
    @Published var isRecording = false
    @Published var sampleCount = 0
    @Published var measuredRateHz: Double = 0
    @Published var statusMessage = "Ready"
    @Published var exercise = "deadlift"

    private let workout = WorkoutManager()
    private let recorder = MotionRecorder()
    private let connectivity = WatchConnectivityManager.shared

    init() {
        // Mirror the recorder's live counters (both are @MainActor-isolated).
        recorder.$sampleCount.assign(to: &$sampleCount)
        recorder.$measuredRateHz.assign(to: &$measuredRateHz)
    }

    var targetRateHz: Int { recorder.targetRateHz }

    func toggle() {
        if isRecording { stop() } else { start() }
    }

    private func start() {
        Task {
            do {
                try await workout.requestAuthorization()
                try workout.start()
                recorder.start()
                isRecording = true
                statusMessage = "Recording…"
            } catch {
                statusMessage = "Error: \(error.localizedDescription)"
            }
        }
    }

    private func stop() {
        recorder.stop()
        workout.stop()
        isRecording = false
        statusMessage = "Saving…"
        Task { await saveAndSend() }
    }

    private func saveAndSend() async {
        let samples = recorder.capturedSamples
        guard !samples.isEmpty else {
            statusMessage = "No samples captured"
            return
        }
        do {
            let result = try SessionWriter.write(
                samples: samples,
                exercise: exercise,
                rateHint: targetRateHz,
                // The clock anchor captured at record start (uptime↔UTC); fall back
                // to now/0 only if a recording somehow produced samples without it.
                startedAt: recorder.startWallClock ?? Date(),
                clockAnchorUptimeSeconds: recorder.startUptimeSeconds ?? 0
            )
            connectivity.sendFile(result.csv, metadata: ["kind": "csv", "exercise": exercise])
            connectivity.sendFile(result.json, metadata: ["kind": "json", "exercise": exercise])
            statusMessage = "Sent \(samples.count) samples"
        } catch {
            statusMessage = "Save failed: \(error.localizedDescription)"
        }
    }
}
