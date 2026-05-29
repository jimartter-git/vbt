import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var controller: RecordingController

    var body: some View {
        VStack(spacing: 8) {
            Text(controller.exercise.capitalized)
                .font(.headline)

            // Live sample count + measured rate. Watching the rate sit near the
            // target (≈200 Hz) is how we confirm the sensor isn't being
            // throttled during a real workout session.
            VStack(spacing: 2) {
                Text("\(controller.sampleCount)")
                    .font(.system(.title2, design: .rounded).monospacedDigit())
                Text(String(format: "%.0f / %d Hz", controller.measuredRateHz, controller.targetRateHz))
                    .font(.caption2)
                    .foregroundStyle(rateColor)
            }

            Button(action: controller.toggle) {
                Label(
                    controller.isRecording ? "Stop" : "Start",
                    systemImage: controller.isRecording ? "stop.fill" : "record.circle"
                )
            }
            .tint(controller.isRecording ? .red : .green)

            Text(controller.statusMessage)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }

    private var rateColor: Color {
        guard controller.isRecording, controller.measuredRateHz > 0 else { return .secondary }
        let ratio = controller.measuredRateHz / Double(controller.targetRateHz)
        return ratio > 0.8 ? .green : .orange
    }
}

#Preview {
    ContentView().environmentObject(RecordingController())
}
