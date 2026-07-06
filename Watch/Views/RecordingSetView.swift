import SwiftUI
import VBTCore

/// Shown while a velocity set is actively recording motion. Big number =
/// live sample count; the Hz readout below it is how we confirm the sensor
/// isn't being throttled (target ~200 Hz on Series 8 / SE2 / Ultra).
struct RecordingSetView: View {
    let metadata: SetMetadata
    @EnvironmentObject private var controller: WorkoutController

    var body: some View {
        VStack(spacing: 6) {
            Text("\(metadata.lift.displayName) \(metadata.setIndex)")
                .font(.headline)

            HStack(spacing: 6) {
                Image(systemName: "heart.fill")
                    .foregroundStyle(.red)
                Text(controller.latestBpm > 0 ? "\(Int(controller.latestBpm))" : "—")
                    .font(.system(.caption, design: .rounded).monospacedDigit())
                Spacer()
                if let rpe = metadata.rpe {
                    Text("RPE \(String(format: "%.1f", rpe))")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Text("\(controller.sampleCount)")
                .font(.system(.title2, design: .rounded).monospacedDigit())
            Text(String(format: "%.0f / %d Hz", controller.measuredRateHz, controller.targetRateHz))
                .font(.caption2)
                .foregroundStyle(rateColor)

            Button(role: .destructive, action: controller.stopSet) {
                Label("Stop Set", systemImage: "stop.fill")
            }

            Text(controller.statusMessage)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 8)
    }

    private var rateColor: Color {
        guard controller.measuredRateHz > 0 else { return .secondary }
        let ratio = controller.measuredRateHz / Double(controller.targetRateHz)
        return ratio > 0.8 ? .green : .orange
    }
}

#Preview {
    RecordingSetView(metadata: SetMetadata(lift: .bench, setIndex: 3))
        .environmentObject(WorkoutController())
}
