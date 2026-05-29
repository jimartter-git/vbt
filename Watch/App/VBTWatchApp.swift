import SwiftUI

@main
struct VBTWatchApp: App {
    @StateObject private var controller = RecordingController()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(controller)
        }
    }
}
