import SwiftUI
import VBTCore

/// The metadata form shown when the lifter taps "Tag Set". Prefilled from
/// `SetMetadataStore.nextSuggestedMetadata()`, so a back-off set is usually
/// a one-scroll confirmation.
struct TagSetView: View {
    @State var metadata: SetMetadata
    @State private var customLift: String
    @State private var loadText: String
    @State private var showOptions = false

    let onConfirm: (SetMetadata) -> Void
    let onCancel: () -> Void

    init(
        initialMetadata: SetMetadata,
        onConfirm: @escaping (SetMetadata) -> Void,
        onCancel: @escaping () -> Void
    ) {
        _metadata = State(initialValue: initialMetadata)
        _customLift = State(initialValue: initialMetadata.customLiftCode ?? "")
        _loadText = State(initialValue: initialMetadata.load.map { formatLoad($0) } ?? "")
        self.onConfirm = onConfirm
        self.onCancel = onCancel
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Text("Tag Set")
                    .font(.headline)

                // Required: lift + set index.
                Picker("Lift", selection: $metadata.lift) {
                    ForEach(Lift.allCases, id: \.self) { lift in
                        Text(lift.displayName).tag(lift)
                    }
                }

                if metadata.lift == .other {
                    TextField("Code (e.g. OHP)", text: $customLift)
                        .textInputAutocapitalization(.characters)
                }

                Stepper("Set \(metadata.setIndex)", value: $metadata.setIndex, in: 1...30)

                // Toggle the optional-metadata drawer. Everything below is
                // sticky from the last set — usually already correct.
                Button(action: { showOptions.toggle() }) {
                    Label(showOptions ? "Hide options" : "Options",
                          systemImage: showOptions ? "chevron.up" : "chevron.down")
                }
                .buttonStyle(.plain)
                .foregroundStyle(.blue)

                if showOptions {
                    optionalFields
                }

                Button(action: confirm) {
                    Label("Start Recording", systemImage: "record.circle")
                }
                .tint(.green)

                Button("Cancel", role: .cancel, action: onCancel)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 6)
        }
    }

    private var optionalFields: some View {
        VStack(alignment: .leading, spacing: 6) {
            Picker("Mount", selection: $metadata.mount) {
                ForEach(WatchMount.allCases, id: \.self) { m in
                    Text(m.displayName).tag(m)
                }
            }

            HStack {
                TextField("Load", text: $loadText)
                Picker("", selection: $metadata.loadUnit) {
                    ForEach(SetMetadata.LoadUnit.allCases, id: \.self) { u in
                        Text(u.displayName).tag(u)
                    }
                }
                .frame(width: 60)
            }

            HStack {
                Text("RPE")
                Spacer()
                Text(metadata.rpe.map { String(format: "%.1f", $0) } ?? "—")
                    .foregroundStyle(.secondary)
            }
            Slider(
                value: Binding(
                    get: { metadata.rpe ?? 7.5 },
                    set: { metadata.rpe = $0 }
                ),
                in: 5.0...10.0,
                step: 0.5
            )

            Picker("Plates", selection: $metadata.plateType) {
                ForEach(PlateType.allCases, id: \.self) { p in
                    Text(p.displayName).tag(p)
                }
            }

            TextField("Notes", text: Binding(
                get: { metadata.notes ?? "" },
                set: { metadata.notes = $0.isEmpty ? nil : $0 }
            ))
        }
    }

    private func confirm() {
        var out = metadata
        out.customLiftCode = customLift.isEmpty ? nil : customLift
        out.load = Double(loadText.trimmingCharacters(in: .whitespaces))
        onConfirm(out)
    }
}

private func formatLoad(_ v: Double) -> String {
    v.truncatingRemainder(dividingBy: 1) == 0
        ? String(Int(v))
        : String(v)
}

#Preview {
    TagSetView(
        initialMetadata: SetMetadata(),
        onConfirm: { _ in },
        onCancel: {}
    )
}
