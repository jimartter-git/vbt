import SwiftUI

/// Idle state: prompt the lifter to start the outer workout.
struct HomeView: View {
    @EnvironmentObject private var controller: WorkoutController

    var body: some View {
        VStack(spacing: 10) {
            Text("VBT")
                .font(.title3)
                .fontWeight(.semibold)

            Text("Start a workout to log heart rate, then tag any set whose velocity you want to track.")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            Button(action: controller.startWorkout) {
                Label("Start Workout", systemImage: "figure.strengthtraining.traditional")
            }
            .tint(.green)

            Text(controller.statusMessage)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

#Preview {
    HomeView().environmentObject(WorkoutController())
}
