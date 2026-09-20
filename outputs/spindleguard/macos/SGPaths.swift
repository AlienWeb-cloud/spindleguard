// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

enum SGPaths {
    static func projectRoot() -> URL {
        if let env = ProcessInfo.processInfo.environment["SPINDLEGUARD_ROOT"], !env.isEmpty {
            return URL(fileURLWithPath: env)
        }
        if let res = Bundle.main.resourceURL {
            let marker = res.appendingPathComponent("sg")
            if FileManager.default.isReadableFile(atPath: marker.path) {
                return res
            }
        }
        var dir = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        if let exe = Bundle.main.executableURL {
            dir = exe.deletingLastPathComponent()
        }
        for _ in 0..<10 {
            if FileManager.default.isReadableFile(atPath: dir.appendingPathComponent("sg").path) {
                return dir
            }
            dir.deleteLastPathComponent()
        }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }

    static func brokerBinary() -> URL {
        let root = projectRoot()
        let built = root.appendingPathComponent("build/spindleguard")
        if FileManager.default.isExecutableFile(atPath: built.path) {
            return built
        }
        return Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/spindleguard")
    }

    static func sgCLI() -> URL {
        projectRoot().appendingPathComponent("sg")
    }

    static func python3() -> String {
        let candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
        ]
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return path
        }
        return "/usr/bin/python3"
    }

    static func exampleManifest() -> URL {
        locate("example-manifest.json", fallback: "macos/Resources/example-manifest.json")
    }

    static func exampleFixture() -> URL {
        locate("example-fixture.json", fallback: "macos/Resources/example-fixture.json")
    }

    static func exampleFailingManifest() -> URL {
        locate("example-failing-manifest.json", fallback: "macos/Resources/example-failing-manifest.json")
    }

    private static func locate(_ name: String, fallback: String) -> URL {
        let root = projectRoot()
        let bundled = root.appendingPathComponent(name)
        if FileManager.default.isReadableFile(atPath: bundled.path) {
            return bundled
        }
        return root.appendingPathComponent(fallback)
    }
}
