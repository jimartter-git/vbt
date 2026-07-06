import SwiftUI

/// During a running workout: live HR readout, list of tagged sets, and the
/// two actions (Tag Set / End Workout).
struct WorkoutView: View {
    @EnvironmentObject private var controller: WorkoutController
    @State private var showTagSheet = false

    var body: some View {
        VStack(spacing: 6) {
            heartRateRow

            Divider()

            if controller.completedSets.isEmpty {
                Text("No velocity sets tagged yet.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 4)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(controller.completedSets.indices, id: \.self) { i in
                            let s = controller.completedSets[i]
                            Text("\(s.lift.displayName) \(s.setIndex)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }

            Button(action: { showTagSheet = true }) {
                Label("Tag Set", systemImage: "plus.circle.fill")
            }
            .tint(.blue)

            Button(role: .destructive, action: controller.endWorkout) {
                Label("End Workout", systemImage: "stop.circle")
            }

            Text(controller.statusMessage)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 8)
        .sheet(isPresented: $showTagSheet) {
            TagSetView(
                initialMetadata: controller.nextSuggestedSetMetadata(),
                onConfirm: { metadata in
                    showTagSheet = false
                    controller.startSet(with: metadata)
                },
                onCancel: { showTagSheet = false }
            )
        }
    }

    private var heartRateRow: some View {
        HStack(spacing: 6) {
            Image(systemName: "heart.fill")
                .foregroundStyle(.red)
            if controller.latestBpm > 0 {
                Text("\(Int(controller.latestBpm))")
                    .font(.system(.title3, design: .rounded).monospacedDigit())
                Text("bpm")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            } else {
                Text("—")
                    .font(.system(.title3, design: .rounded).monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
    }
}

#Preview {
    WorkoutView().environmentObject(WorkoutController())
}
