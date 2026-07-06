import SwiftUI

/// Root of the watch UI. Routes on the outer workout phase:
/// - idle              → HomeView (Start Workout)
/// - workoutRunning    → WorkoutView (HR + tagged sets + Tag Set / End)
/// - setRecording(m)   → RecordingSetView (live rate + Stop Set)
struct ContentView: View {
    @EnvironmentObject private var controller: WorkoutController

    var body: some View {
        switch controller.phase {
        case .idle:
            HomeView()
        case .workoutRunning:
            WorkoutView()
        case .setRecording(let metadata):
            RecordingSetView(metadata: metadata)
        }
    }
}

#Preview {
    ContentView().environmentObject(WorkoutController())
}
