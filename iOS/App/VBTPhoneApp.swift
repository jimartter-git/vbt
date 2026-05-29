import SwiftUI

@main
struct VBTPhoneApp: App {
    @StateObject private var connectivity = PhoneConnectivity.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(connectivity)
        }
    }
}
