import Foundation
import AVFoundation
import Combine
import UIKit
import VBTCore

/// HD60, no-audio video capture for the phone-as-hub capture rig (Phase 1 of
/// `docs/capture-app.md`). Owns an `AVCaptureSession` configured for 1080p60 HEVC
/// to the back camera and writes each set to a `.mov` plus a `RecordingMetadata`
/// JSON sidecar (the SAME envelope the watch writes, so video and watch share the
/// uptime↔UTC clock anchor used for cross-source sync — learning #23).
///
/// NO audio by design (`docs/capture-app.md`): we never add an audio input or touch
/// the audio session, which keeps the AirPods motion route clean for Phase 2 and
/// avoids routing the AirPods mic into call-mode.
///
/// Threading follows the AVCam pattern: all session work runs on `sessionQueue`
/// (off-main, per Apple guidance); `@Published` UI state is published on the main
/// queue via `publish(_:)`. Not `@MainActor` for that reason.
///
/// FIRST-BUILD TODOs (no Xcode in the analysis container — author + flag):
///   • Verify a 1080p60 `AVCaptureDevice.Format` exists on the target iPhone and that
///     `selectBestFormat` picks it (fallback: highest fps found at 1080p).
///   • Confirm HEVC is accepted on the active connection; H.264 is the fallback.
///   • Under stricter concurrency checking, the cross-thread `pendingMeta` access
///     (set on start, read in the delegate) may want a small lock or sessionQueue hop.
///   • `NSCameraUsageDescription` is set in iOS/Resources/Info.plist (done).
final class VideoRecorder: NSObject, ObservableObject {
    enum State: Equatable { case idle, configuring, ready, recording, denied, failed(String) }

    @Published private(set) var state: State = .idle
    @Published private(set) var lastFileURL: URL?
    @Published private(set) var measuredFPS: Double = 0

    /// Exposed so the SwiftUI preview can attach an `AVCaptureVideoPreviewLayer`.
    let session = AVCaptureSession()

    private let sessionQueue = DispatchQueue(label: "com.vbt.video.session")
    private let movieOutput = AVCaptureMovieFileOutput()
    private var videoDevice: AVCaptureDevice?

    private let requestedFPS: Double = 60
    private let requestedHeight = 1080

    /// Set at `start`; persisted into the sidecar so the .mov is time-alignable.
    private var pendingMeta: RecordingMetadata?

    private let storeDir: URL = {
        let dir = URL.documentsDirectory.appendingPathComponent("Captures", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    private func publish(_ block: @escaping () -> Void) {
        if Thread.isMainThread { block() } else { DispatchQueue.main.async(execute: block) }
    }

    // MARK: - Setup

    /// Request camera permission and build the capture graph. Idempotent; call from main.
    func configure() {
        guard state == .idle else { return }
        publish { self.state = .configuring }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            sessionQueue.async { [weak self] in self?.buildSession() }
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                guard let self else { return }
                if granted { self.sessionQueue.async { self.buildSession() } }
                else { self.publish { self.state = .denied } }
            }
        default:
            publish { self.state = .denied }
        }
    }

    /// Build the session on `sessionQueue`. Selects the best 1080p60 format, wires the
    /// back camera + movie output, pins HEVC.
    private func buildSession() {
        session.beginConfiguration()
        session.sessionPreset = .inputPriority   // we drive resolution via activeFormat

        guard
            let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else {
            session.commitConfiguration()
            publish { self.state = .failed("No usable back camera") }
            return
        }
        session.addInput(input)
        videoDevice = device

        guard session.canAddOutput(movieOutput) else {
            session.commitConfiguration()
            publish { self.state = .failed("Cannot add movie output") }
            return
        }
        session.addOutput(movieOutput)

        selectBestFormat(on: device)

        // Prefer HEVC for size; harmless if the connection ignores it.
        if let connection = movieOutput.connection(with: .video) {
            if movieOutput.availableVideoCodecTypes.contains(.hevc) {
                movieOutput.setOutputSettings([AVVideoCodecKey: AVVideoCodecType.hevc], for: connection)
            }
            connection.videoOrientation = .portrait   // tripod is portrait; rotation honored on decode (#22)
        }

        session.commitConfiguration()
        session.startRunning()
        publish { self.state = .ready }
    }

    /// Pick the format with the requested height that supports the requested fps
    /// (or the closest available), then lock the frame duration to that fps.
    private func selectBestFormat(on device: AVCaptureDevice) {
        let target = device.formats.first { f in
            let dims = CMVideoFormatDescriptionGetDimensions(f.formatDescription)
            return Int(dims.height) == requestedHeight
                && f.videoSupportedFrameRateRanges.contains { $0.maxFrameRate >= requestedFPS }
        }
        let chosen = target ?? device.formats.max { a, b in
            let am = a.videoSupportedFrameRateRanges.map(\.maxFrameRate).max() ?? 0
            let bm = b.videoSupportedFrameRateRanges.map(\.maxFrameRate).max() ?? 0
            return am < bm
        }
        guard let format = chosen, (try? device.lockForConfiguration()) != nil else { return }
        device.activeFormat = format
        let fps = min(requestedFPS,
                      format.videoSupportedFrameRateRanges.map(\.maxFrameRate).max() ?? requestedFPS)
        let duration = CMTime(value: 1, timescale: Int32(fps.rounded()))
        device.activeVideoMinFrameDuration = duration
        device.activeVideoMaxFrameDuration = duration
        device.unlockForConfiguration()
        publish { self.measuredFPS = fps }
    }

    // MARK: - Record

    /// Start recording a set. `meta` carries the shared setId + UTC/uptime anchor
    /// (built by `SetCaptureController` so every stream stamps the same instant).
    /// Call from main.
    func start(meta: RecordingMetadata) {
        guard state == .ready else { return }
        pendingMeta = meta
        let url = storeDir.appendingPathComponent(meta.fileStem).appendingPathExtension("mov")
        publish { self.state = .recording }
        sessionQueue.async { [weak self] in
            guard let self else { return }
            try? FileManager.default.removeItem(at: url)
            self.movieOutput.startRecording(to: url, recordingDelegate: self)
        }
    }

    func stop() {
        guard state == .recording else { return }
        sessionQueue.async { [weak self] in self?.movieOutput.stopRecording() }
    }
}

// MARK: - File output delegate

extension VideoRecorder: AVCaptureFileOutputRecordingDelegate {
    func fileOutput(
        _ output: AVCaptureFileOutput,
        didFinishRecordingTo outputFileURL: URL,
        from connections: [AVCaptureConnection],
        error: Error?
    ) {
        if let error {
            publish { self.state = .failed(error.localizedDescription) }
            return
        }
        writeSidecar(for: outputFileURL)
        publish {
            self.lastFileURL = outputFileURL
            self.state = .ready
        }
    }

    /// Write the `<stem>.json` envelope next to the `.mov` so the video carries the
    /// same uptime↔UTC anchor as the watch CSV (cross-source alignment, #23).
    private func writeSidecar(for movieURL: URL) {
        guard var meta = pendingMeta else { return }
        let asset = AVURLAsset(url: movieURL)
        let fps = measuredFPS > 0 ? measuredFPS : requestedFPS
        meta.sampleCount = max(0, Int(CMTimeGetSeconds(asset.duration) * fps))
        meta.deviceModel = UIDevice.current.model
        meta.osVersion = UIDevice.current.systemVersion
        let json = movieURL.deletingPathExtension().appendingPathExtension("json")
        if let data = try? JSONEncoder().encode(meta) { try? data.write(to: json) }
        pendingMeta = nil
    }
}
</content>
