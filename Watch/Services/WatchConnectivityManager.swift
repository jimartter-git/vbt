import Foundation
import WatchConnectivity

/// Ships recorded session files from the watch to the paired iPhone.
/// `transferFile` is queued and reliable (survives the apps not both being
/// foregrounded), which is what we want for offline analysis — see
/// docs/architecture.md.
final class WatchConnectivityManager: NSObject, ObservableObject {
    static let shared = WatchConnectivityManager()

    override init() {
        super.init()
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    /// Queue a recorded CSV (and its metadata) for transfer to the phone.
    @discardableResult
    func sendFile(_ url: URL, metadata: [String: Any]? = nil) -> WCSessionFileTransfer? {
        guard WCSession.default.activationState == .activated else { return nil }
        return WCSession.default.transferFile(url, metadata: metadata)
    }
}

extension WatchConnectivityManager: WCSessionDelegate {
    func session(
        _ session: WCSession,
        activationDidCompleteWith activationState: WCSessionActivationState,
        error: Error?
    ) {}

    func session(_ session: WCSession, didFinish fileTransfer: WCSessionFileTransfer, error: Error?) {}
}
