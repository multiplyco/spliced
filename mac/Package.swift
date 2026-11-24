// swift-tools-version:5.9
// Spliced for Mac: a native window around the same app `spliced open` serves. Built by build.sh into Spliced.app.
import PackageDescription

let package = Package(
    name: "Spliced",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(name: "Spliced", path: "Sources/Spliced"),
    ]
)
