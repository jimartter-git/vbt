import SwiftUI
import AVFoundation

/// Phase 1 capture screen: live camera preview + a record button, with the
/// Bluetooth clicker (`CaptureEventController`) installed on the preview view so a
/// shutter press toggles the set. See `docs/capture-app.md`.
struct CaptureView: View {
    @StateObject private var controller = SetCaptureController()

    private let exercises = ["deadlift", "squat", "bench", "row", "rdl"]

    var body: some View {
        ZStack {
            CameraPreview(session: controller.video.session, clicker: controller.clicker)
                .ignoresSafeArea()

            VStack {
                Picker("Lift", selection: $controller.exercise) {
                    ForEach(exercises, id: \.self) { Text($0.capitalized).tag($0) }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
                .padding()
                .disabled(controller.isRecording)

                Spacer()

                Text(controller.statusMessage)
                    .font(.callout.monospaced())
                    .padding(8)
                    .background(.ultraThinMaterial, in: Capsule())

                Button(action: controller.toggle) {
                    Circle()
                        .fill(controller.isRecording ? Color.red : Color.white)
                        .frame(width: 74, height: 74)
                        .overlay(Circle().stroke(.white, lineWidth: 4).frame(width: 86, height: 86))
                }
                .padding(.bottom, 28)
            }
        }
        .onAppear { controller.arm() }
    }
}

/// Hosts an `AVCaptureVideoPreviewLayer` for the session AND installs the clicker
/// interaction on the same view (the interaction must live on a real UIView).
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    let clicker: CaptureEventController

    func makeUIView(context: Context) -> PreviewUIView {
        let view = PreviewUIView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        clicker.install(on: view)          // clicker / hardware buttons → record toggle
        return view
    }

    func updateUIView(_ uiView: PreviewUIView, context: Context) {}

    /// A UIView backed by an `AVCaptureVideoPreviewLayer` (so the layer resizes with
    /// the view automatically).
    final class PreviewUIView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
}
</content>
