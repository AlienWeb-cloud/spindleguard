// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI

@main
struct SpindleGuardApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup("SpindleGuard") {
            ContentView()
                .environmentObject(state)
                .frame(minWidth: 980, minHeight: 640)
        }
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Disposable Session") { state.newSession() }
                    .keyboardShortcut("n", modifiers: [.command])
                Button("Load Session…") { state.loadSession() }
                    .keyboardShortcut("o", modifiers: [.command])
            }
            CommandMenu("Setup") {
                Button("Preview Setup") { state.previewSetup() }
                Button("Run Setup") { state.runSetup() }
                    .keyboardShortcut("s", modifiers: [.command, .shift])
                Button("Verify Install") { state.verifyInstall() }
                    .keyboardShortcut("k", modifiers: [.command, .shift])
                Divider()
                Button("Install FUSE-T…") { state.installFuse() }
                Button("Copy FUSE-T Command") { state.copyFuseCommand() }
                Button("Open FUSE-T Docs") { state.openFuseDocs() }
                Button("Refresh Doctor") { state.refreshDoctor() }
            }
            CommandMenu("Broker") {
                Button("Start") { state.start() }
                    .keyboardShortcut("r", modifiers: [.command])
                    .disabled(state.running)
                Button("Stop") { state.stop() }
                    .keyboardShortcut(".", modifiers: [.command])
                    .disabled(!state.running)
                Button("Unmount") { state.unmountOnly() }
                    .disabled(state.mount.isEmpty)
                Button("Policy Check") { state.policyCheck() }
                Button("Preview Start") { state.previewStart() }
                Divider()
                Button("Open Mount in Finder") { state.openMount() }
                    .disabled(state.mount.isEmpty)
                Button("Open Source in Finder") { state.openSource() }
                    .disabled(state.source.isEmpty)
                Button("Reveal Log") { state.revealLog() }
                    .disabled(state.logPath.isEmpty)
                Button("Probe Queue") { state.probeQueue() }
                    .keyboardShortcut("p", modifiers: [.command])
                    .disabled(!state.running)
            }
            CommandMenu("Control") {
                Button("Scan Tree") { state.scanTree() }
                Button("Bind Example Identity") { state.bindIdentity() }
                Button("Resolve Topology") { state.runTopology() }
                    .disabled(state.source.isEmpty)
                Button("Rotate Manifest") { state.rotateManifest() }
            }
        }
        Settings {
            VStack(alignment: .leading, spacing: 12) {
                Text("SpindleGuard is a test-only prototype.")
                    .font(.headline)
                Text("It does not protect evidence drives or confine agents. Source and mount under /Volumes or /dev are refused. Session files are retained.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: 360, alignment: .leading)
                Text("Session parent")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(state.sessionParentPath)
                    .font(.caption.monospaced())
                    .textSelection(.enabled)
                Text(state.fuseInstall)
                    .font(.caption.monospaced())
                    .textSelection(.enabled)
            }
            .padding(24)
        }
    }
}
