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
        let bundledApp = root.appendingPathComponent("SpindleGuard.app/Contents/Helpers/spindleguard")
        if FileManager.default.isExecutableFile(atPath: bundledApp.path) {
            return bundledApp
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

    /// Writable session parent. Prefers `<project>/work`; if the bundle
    /// resources are not writable, uses Application Support. Never /Volumes.
    static func sessionParent() -> URL {
        if let env = ProcessInfo.processInfo.environment["SPINDLEGUARD_SESSION_PARENT"], !env.isEmpty {
            return URL(fileURLWithPath: env)
        }
        let work = projectRoot().appendingPathComponent("work")
        let marker = work.appendingPathComponent(".spindleguard-session-parent")
        do {
            try FileManager.default.createDirectory(at: work, withIntermediateDirectories: true)
            if !FileManager.default.fileExists(atPath: marker.path) {
                try "retained session parent\n".write(to: marker, atomically: true, encoding: .utf8)
            }
            return work
        } catch {
            let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
                ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
            let parent = base.appendingPathComponent("SpindleGuard/sessions", isDirectory: true)
            try? FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
            return parent
        }
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
