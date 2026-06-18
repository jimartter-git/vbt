import SwiftUI

@main
struct VBTPhoneApp: App {
    @StateObject private var connectivity = PhoneConnectivity.shared

    var body: some Scene {
        WindowGroup {
            TabView {
                CaptureView()
                    .tabItem { Label("Capture", systemImage: "camera") }
                ContentView()
                    .environmentObject(connectivity)
                    .tabItem { Label("Sessions", systemImage: "applewatch") }
            }
        }
    }
}
