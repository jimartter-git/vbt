import Foundation
import Combine
import VBTCore

/// The unified "set" controller — the hub that one clicker press drives
/// (`docs/capture-app.md`). Phase 1 owns the video recorder and the shared
/// per-set identity + clock anchor; the AirPods (Phase 2) and watch (Phase 3)
/// streams plug into the SAME start/stop so every source stamps one instant.
///
/// The clock anchor is the crux: `startedAt` (UTC) + `clockAnchorUptimeSeconds`
/// (device uptime captured at the same instant) is the only thing that ties a
/// recording to absolute time. Video frame PTS are on the host (uptime) clock, so
/// the video shares this anchor exactly; the watch — a separate device/clock — is
/// coarse-aligned by the same UTC and then refined by velocity cross-correlation
/// (learning #23). Stamping ONE anchor across all streams at start is what makes
/// fusion possible.
@MainActor
final class SetCaptureController: ObservableObject {
    @Published var exercise = "deadlift"
    @Published private(set) var isRecording = false
    @Published private(set) var statusMessage = "Tap to set up camera"

    let video = VideoRecorder()
    let clicker = CaptureEventController()

    private var cancellables = Set<AnyCancellable>()

    init() {
        // One clicker press toggles the whole set. Wire BOTH volume keys: a BT clicker
        // may emit volume-up (→ secondary) or volume-down (→ primary), and the stock
        // Camera app maps both to the shutter, so we mirror that — either toggles.
        clicker.onPrimary = { [weak self] in self?.toggle() }
        clicker.onSecondary = { [weak self] in self?.toggle() }
        // Surface the video recorder's state in the UI.
        video.$state
            .receive(on: RunLoop.main)
            .sink { [weak self] state in self?.reflect(state) }
            .store(in: &cancellables)
    }

    /// Bring the camera up (permission + session). Call when the capture screen appears.
    func arm() {
        if case .idle = video.state { video.configure() }
    }

    func toggle() {
        if isRecording { stop() } else { start() }
    }

    private func start() {
        guard case .ready = video.state else { return }
        // ONE identity + ONE clock anchor for every stream in this set.
        let meta = RecordingMetadata(
            startedAt: Date(),
            clockAnchorUptimeSeconds: ProcessInfo.processInfo.systemUptime,
            exercise: exercise,
            sampleRateHintHz: 60
        )
        video.start(meta: meta)
        isRecording = true
        statusMessage = "Recording…"

        // PHASE 2 TODO — start AirPods head-motion capture here with the same `meta`
        //   (CMHeadphoneMotionManager → <stem>_airpods.csv).
        // PHASE 3 TODO — send a WCSession start marker to the (armed, backgrounded)
        //   watch here so the clicker drives the watch too (arm-once model).
    }

    private func stop() {
        video.stop()
        isRecording = false
        statusMessage = "Saving…"

        // PHASE 2 TODO — stop AirPods capture + write its sidecar.
        // PHASE 3 TODO — send the WCSession stop marker to the watch.
    }

    private func reflect(_ state: VideoRecorder.State) {
        switch state {
        case .idle, .configuring: statusMessage = "Setting up camera…"
        case .ready where !isRecording: statusMessage = "Ready — clicker or tap to record"
        case .ready: statusMessage = "Saved"
        case .recording: statusMessage = "Recording…"
        case .denied: statusMessage = "Camera access denied — enable it in Settings"
        case .failed(let msg): statusMessage = "Camera error: \(msg)"
        }
    }
}
</content>
