import Foundation
import WatchConnectivity

/// Thin relay: receives session files transferred from the watch and persists
/// them in Documents (also exposed via the Files app so raw CSVs can be pulled
/// to a Mac for offline Python analysis).
@MainActor
final class PhoneConnectivity: NSObject, ObservableObject {
    static let shared = PhoneConnectivity()

    @Published private(set) var sessions: [URL] = []

    /// Immutable + Sendable, so it's safe to touch from nonisolated delegate
    /// callbacks (which arrive on a background thread).
    private let storeDir: URL

    override init() {
        storeDir = URL.documentsDirectory.appendingPathComponent("Sessions", isDirectory: true)
        super.init()
        try? FileManager.default.createDirectory(at: storeDir, withIntermediateDirectories: true)
        refresh()

        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    func refresh() {
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: storeDir,
            includingPropertiesForKeys: [.contentModificationDateKey]
        )) ?? []
        sessions = urls
            .filter { $0.pathExtension == "csv" }
            .sorted { lhs, rhs in
                let l = (try? lhs.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
                let r = (try? rhs.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
                return l > r
            }
    }

    func delete(_ url: URL) {
        try? FileManager.default.removeItem(at: url)
        // Also remove the JSON sidecar if present.
        let json = url.deletingPathExtension().appendingPathExtension("json")
        try? FileManager.default.removeItem(at: json)
        refresh()
    }

    /// Copies an incoming transfer into the store. Must complete synchronously:
    /// the source temp file is removed once the delegate call returns.
    nonisolated private func persist(_ fileURL: URL) {
        let dest = storeDir.appendingPathComponent(fileURL.lastPathComponent)
        try? FileManager.default.removeItem(at: dest)
        do {
            try FileManager.default.copyItem(at: fileURL, to: dest)
        } catch {
            return
        }
        Task { @MainActor in self.refresh() }
    }
}

extension PhoneConnectivity: WCSessionDelegate {
    nonisolated func session(
        _ session: WCSession,
        activationDidCompleteWith activationState: WCSessionActivationState,
        error: Error?
    ) {}

    nonisolated func sessionDidBecomeInactive(_ session: WCSession) {}

    nonisolated func sessionDidDeactivate(_ session: WCSession) {
        // Reactivate so we keep receiving from the watch after a switch.
        session.activate()
    }

    nonisolated func session(_ session: WCSession, didReceive file: WCSessionFile) {
        persist(file.fileURL)
    }
}
