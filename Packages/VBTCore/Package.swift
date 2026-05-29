// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "VBTCore",
    platforms: [
        .iOS(.v17),
        .watchOS(.v10),
    ],
    products: [
        .library(name: "VBTCore", targets: ["VBTCore"]),
    ],
    targets: [
        .target(name: "VBTCore"),
        .testTarget(name: "VBTCoreTests", dependencies: ["VBTCore"]),
    ]
)
