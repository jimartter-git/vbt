import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var connectivity: PhoneConnectivity

    var body: some View {
        NavigationStack {
            Group {
                if connectivity.sessions.isEmpty {
                    emptyState
                } else {
                    sessionList
                }
            }
            .navigationTitle("VBT Sessions")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        connectivity.refresh()
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
        }
    }

    private var sessionList: some View {
        List {
            ForEach(connectivity.sessions, id: \.self) { url in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(url.deletingPathExtension().lastPathComponent)
                            .font(.subheadline.monospaced())
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Text(byteSize(of: url))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    ShareLink(item: url) {
                        Image(systemName: "square.and.arrow.up")
                    }
                }
            }
            .onDelete { offsets in
                offsets.map { connectivity.sessions[$0] }.forEach(connectivity.delete)
            }
        }
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Sessions Yet", systemImage: "applewatch")
        } description: {
            Text("Record a set on the watch. Transferred CSVs appear here — share them to your Mac for analysis.")
        }
    }

    private func byteSize(of url: URL) -> String {
        let bytes = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }
}

#Preview {
    ContentView().environmentObject(PhoneConnectivity.shared)
}
