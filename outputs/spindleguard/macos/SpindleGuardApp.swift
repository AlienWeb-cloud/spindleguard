// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI
import AppKit

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
                Button("First-Run Setup Wizard…") { state.openWizard() }
                    .keyboardShortcut("?", modifiers: [.command, .shift])
                Divider()
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
                    .disabled(state.running || state.sessionBucketed || state.sessionPurged)
                Button("Stop") { state.stop() }
                    .keyboardShortcut(".", modifiers: [.command])
                    .disabled(!state.running)
                Button("Unmount") { state.unmountOnly() }
                    .disabled(state.mount.isEmpty)
                Button("Policy Check") { state.policyCheck() }
                Button("Preview Start") { state.previewStart() }
                    .disabled(state.sessionBucketed || state.sessionPurged)
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
                Divider()
                Button("List Retained Sessions") {
                    state.listSessions()
                    state.pane = .retain
                }
                Button("Move Current Session to Bucket") { state.bucketCurrentSession() }
                    .disabled(state.sessionRoot.isEmpty || state.sessionBucketed || state.sessionPurged)
                Button("Purge Bucket") { state.purgeBucket() }
                    .disabled(state.bucket.isEmpty)
                Button("Empty Purged List…") { state.destroyPurged() }
                    .disabled(state.purged.isEmpty)
            }
        }
        MenuBarExtra("SpindleGuard", systemImage: "externaldrive") {
            Text(state.running ? "Mounted" : (state.canMount ? "Idle" : "Setup needed"))
            Text(state.status)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            Section("Window") {
                Button("Show SpindleGuard") { state.showMainWindow() }
                Button("First-Run Setup Wizard…") { state.openWizard() }
            }
            Section("Setup") {
                Button("Preview Setup") {
                    state.revealPane(.setup)
                    state.previewSetup()
                }
                Button("Run Setup") {
                    state.revealPane(.setup)
                    state.runSetup()
                }
                Button("Verify Install") {
                    state.revealPane(.setup)
                    state.verifyInstall()
                }
                Button("Install FUSE-T…") {
                    state.revealPane(.setup)
                    state.installFuse()
                }
                Button("Copy FUSE-T Command") { state.copyFuseCommand() }
                Button("Open FUSE-T Docs") { state.openFuseDocs() }
                Button("Refresh Doctor") {
                    state.revealPane(.doctor)
                    state.refreshDoctor()
                }
            }
            Section("Session") {
                Button("New Disposable Session") { state.newSession() }
                Button("Load Session…") { state.loadSession() }
                Button("Retained Sessions") {
                    state.revealPane(.retain)
                    state.listSessions()
                }
                Button("Move Current Session to Bucket") { state.bucketCurrentSession() }
                    .disabled(state.sessionRoot.isEmpty || state.sessionBucketed || state.sessionPurged)
                Button("Purge Bucket") { state.purgeBucket() }
                    .disabled(state.bucket.isEmpty)
                Button("Empty Purged List…") { state.destroyPurged() }
                    .disabled(state.purged.isEmpty)
                Button("Open Session Parent") { state.openSessionParent() }
            }
            Section("Broker") {
                Button("Start") {
                    state.revealPane(.broker)
                    state.start()
                }
                .disabled(state.running || state.sessionBucketed || state.sessionPurged)
                Button("Stop") { state.stop() }
                    .disabled(!state.running)
                Button("Unmount") { state.unmountOnly() }
                    .disabled(state.mount.isEmpty)
                Button("Policy Check") {
                    state.revealPane(.broker)
                    state.policyCheck()
                }
                Button("Preview Start") {
                    state.revealPane(.broker)
                    state.previewStart()
                }
                .disabled(state.sessionBucketed || state.sessionPurged)
                Button("Open Mount in Finder") { state.openMount() }
                    .disabled(state.mount.isEmpty)
                Button("Open Source in Finder") { state.openSource() }
                    .disabled(state.source.isEmpty)
                Button("Reveal Log") { state.revealLog() }
                    .disabled(state.logPath.isEmpty)
                Button("Probe Queue") {
                    state.revealPane(.queue)
                    state.probeQueue()
                }
                .disabled(!state.running)
            }
            Section("Identity") {
                Button("Scan Tree") {
                    state.revealPane(.identity)
                    state.scanTree()
                }
                Button("Bind Example Identity") {
                    state.revealPane(.identity)
                    state.bindIdentity()
                }
                Button("Load Example Identity") {
                    state.revealPane(.identity)
                    state.loadExampleIdentity()
                }
                Button("Load Failing Example") {
                    state.revealPane(.identity)
                    state.loadFailingExample()
                }
                Button("Rotate Manifest") {
                    state.revealPane(.identity)
                    state.rotateManifest()
                }
                Button("Resolve Topology") {
                    state.revealPane(.topology)
                    state.runTopology()
                }
                .disabled(state.source.isEmpty)
            }
            Divider()
            Button("Quit SpindleGuard") { NSApplication.shared.terminate(nil) }
        }
        .menuBarExtraStyle(.menu)
        Settings {
            VStack(alignment: .leading, spacing: 12) {
                Text("SpindleGuard is a test-only prototype.")
                    .font(.headline)
                Text("It does not protect evidence drives or confine agents. Source and mount under /Volumes or /dev are refused. Three lists: active, bucket, purged. Destroy only from purged.")
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
