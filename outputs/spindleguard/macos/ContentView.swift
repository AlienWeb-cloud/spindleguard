// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI

private let sgBlue = Color(red: 36 / 255, green: 88 / 255, blue: 201 / 255)

struct ContentView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        NavigationSplitView {
            List {
                ForEach(AppState.Pane.allCases) { pane in
                    Button {
                        state.pane = pane
                    } label: {
                        Label(pane.rawValue, systemImage: icon(pane))
                    }
                    .listRowBackground(state.pane == pane ? Color.accentColor.opacity(0.15) : Color.clear)
                }
            }
            .listStyle(.sidebar)
        } detail: {
            VStack(spacing: 0) {
                instrument
                Divider()
                Group {
                    switch state.pane {
                    case .broker: BrokerPane()
                    case .queue: QueuePane()
                    case .identity: IdentityPane()
                    case .topology: TopologyPane()
                    case .doctor: DoctorPane()
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button("New Session", action: state.newSession)
                Button(state.running ? "Stop" : "Start") {
                    state.running ? state.stop() : state.start()
                }
                .keyboardShortcut(state.running ? "." : "r", modifiers: [.command])
                Button("Open Mount", action: state.openMount)
                    .disabled(state.mount.isEmpty)
                Button("Probe Queue", action: state.probeQueue)
                    .disabled(!state.running)
            }
        }
    }

    private var instrument: some View {
        HStack(alignment: .center, spacing: 28) {
            VStack(alignment: .leading, spacing: 4) {
                Text("SPINDLEGUARD")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundStyle(.secondary)
                Text(state.running ? "Mounted" : "Idle")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(state.running ? sgBlue : Color.primary)
            }
            Divider().frame(height: 44)
            metric("ACTIVE", state.running && state.activeOp != "idle" ? "1 / 1" : "0 / 1")
            metric("PENDING", String(state.pending))
            metric("WAIT", String(format: "%.1f ms", state.lastWaitMs))
            metric("OP", state.activeOp.uppercased())
            Spacer()
            if let problem = state.policyProblem, !state.source.isEmpty {
                Text(problem)
                    .font(.caption)
                    .foregroundStyle(Color(red: 0.62, green: 0.27, blue: 0.17))
                    .frame(maxWidth: 280, alignment: .trailing)
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private func metric(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.system(size: 9, weight: .medium, design: .monospaced))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 16, weight: .semibold, design: .monospaced))
        }
    }

    private func icon(_ pane: AppState.Pane) -> String {
        switch pane {
        case .broker: return "externaldrive"
        case .queue: return "list.bullet.rectangle"
        case .identity: return "checkmark.shield"
        case .topology: return "point.3.connected.trianglepath.dotted"
        case .doctor: return "stethoscope"
        }
    }
}
