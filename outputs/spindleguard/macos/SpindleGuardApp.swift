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
            }
            CommandMenu("Broker") {
                Button("Start") { state.start() }
                    .keyboardShortcut("r", modifiers: [.command])
                    .disabled(state.running)
                Button("Stop") { state.stop() }
                    .keyboardShortcut(".", modifiers: [.command])
                    .disabled(!state.running)
                Divider()
                Button("Open Mount in Finder") { state.openMount() }
                    .disabled(state.mount.isEmpty)
                Button("Open Source in Finder") { state.openSource() }
                    .disabled(state.source.isEmpty)
                Button("Probe Queue") { state.probeQueue() }
                    .keyboardShortcut("p", modifiers: [.command])
                    .disabled(!state.running)
            }
            CommandMenu("Control") {
                Button("Refresh Doctor") { state.refreshDoctor() }
                Button("Scan Tree") { state.scanTree() }
                Button("Bind Example Identity") { state.bindIdentity() }
            }
        }
        Settings {
            VStack(alignment: .leading, spacing: 12) {
                Text("SpindleGuard is a test-only prototype.")
                    .font(.headline)
                Text("It does not protect evidence drives or confine agents. Source and mount under /Volumes or /dev are refused. Session files are retained.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: 360, alignment: .leading)
            }
            .padding(24)
        }
    }
}
