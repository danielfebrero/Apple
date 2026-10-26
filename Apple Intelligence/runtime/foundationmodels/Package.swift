// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "AppleSystemModel",
    platforms: [.macOS("26.0")],
    products: [.executable(name: "apple-system-model", targets: ["AppleSystemModel"])],
    targets: [.executableTarget(name: "AppleSystemModel")]
)
