import SwiftUI

@main
struct VBTWatchApp: App {
    @StateObject private var controller = WorkoutController()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(controller)
        }
    }
}
