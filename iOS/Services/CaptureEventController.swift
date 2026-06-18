import Foundation
import UIKit
#if canImport(AVKit)
import AVKit
#endif

/// Bridges the hardware capture buttons — and Bluetooth tripod clickers, which
/// emit a volume-button HID press — to a record toggle, via Apple's sanctioned
/// `AVCaptureEventInteraction` (iOS 17.2+). One press of the clicker's shutter
/// fires `onPrimary`; the secondary (volume-up) is wired too for future use.
///
/// Why this exists: a custom `AVCaptureSession` app gets NOTHING from the volume
/// buttons for free (only the stock Camera app maps volume→shutter). This is the
/// supported opt-in — it also covers the iPhone Action button / Camera Control and
/// AirPods stem clicks (`docs/capture-app.md`).
///
/// FIRST-BUILD TODOs (no Xcode here — author + flag):
///   • Deployment target is iOS 17.0; this API needs 17.2 → guarded with @available.
///     Bump IPHONEOS_DEPLOYMENT_TARGET to 17.2 OR keep the guard (older OS = no
///     hardware trigger, on-screen button still works).
///   • Confirm what THIS clicker emits: ~95% send a volume key (handled here). If it
///     turns out to be an HID keyboard key (e.g. Return), add a `UIKeyCommand` /
///     `pressesBegan` fallback on the hosting view — a 5-minute on-device check.
@MainActor
final class CaptureEventController {
    var onPrimary: () -> Void = {}
    var onSecondary: () -> Void = {}

    private var installed = false

    /// Attach the capture-event interaction to a hosting view (the camera preview).
    func install(on view: UIView) {
        guard !installed else { return }
        installed = true
        #if canImport(AVKit)
        if #available(iOS 17.2, *) {
            let interaction = AVCaptureEventInteraction(
                primary: { [weak self] event in
                    if event.phase == .ended { self?.onPrimary() }
                },
                secondary: { [weak self] event in
                    if event.phase == .ended { self?.onSecondary() }
                }
            )
            interaction.isEnabled = true
            view.addInteraction(interaction)
        }
        #endif
        // Pre-17.2 (or if AVKit is unavailable): no hardware trigger; the on-screen
        // record button remains the path. Intentionally a no-op, not a failure.
    }
}
</content>
