// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI

struct BrokerPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Broker")
                .font(.title2.weight(.semibold))
            Text("Disposable test data only. The prototype refuses /Volumes and /dev, requires a .spindleguard-test-root marker, and serializes backing work through one FIFO queue.")
                .foregroundStyle(.secondary)
            Form {
                LabeledContent("Source") {
                    HStack {
                        TextField("Source directory", text: $state.source)
                        Button("Choose…") {
                            state.chooseDirectory(title: "Choose disposable source") { state.source = $0 }
                        }
                    }
                }
                LabeledContent("Mount") {
                    HStack {
                        TextField("Mount directory", text: $state.mount)
                        Button("Choose…") {
                            state.chooseDirectory(title: "Choose empty mount point") { state.mount = $0 }
                        }
                    }
                }
                Toggle("Allow writes under prefix", isOn: $state.writable)
                if state.writable {
                    TextField("Write prefix", text: $state.writePrefix)
                }
                LabeledContent("Read delay") {
                    HStack {
                        Slider(value: $state.delayMs, in: 0...500, step: 10)
                        Text("\(Int(state.delayMs)) ms")
                            .font(.body.monospacedDigit())
                            .frame(width: 64, alignment: .trailing)
                    }
                }
            }
            .formStyle(.grouped)
            HStack {
                Button("Open Source") { state.openSource() }
                    .disabled(state.source.isEmpty)
                Button("Open Mount") { state.openMount() }
                    .disabled(state.mount.isEmpty)
                Spacer()
            }
            statusBlock
        }
    }

    private var statusBlock: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(state.status)
            if !state.error.isEmpty {
                Text(state.error)
                    .foregroundStyle(.red)
            }
            Text("Session files and broker.jsonl are retained. This app does not delete.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
    }
}

struct QueuePane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Queue")
                .font(.title2.weight(.semibold))
            Text("Live stderr from the C broker. A competing request should wait while one backing callback is active.")
                .foregroundStyle(.secondary)
            HStack {
                Button("Probe concurrent reads") { state.probeQueue() }
                    .disabled(!state.running)
                if !state.probeJSON.isEmpty {
                    Text("Probe result below")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Table(Array(state.events.suffix(200).reversed())) {
                TableColumn("Event") { event in Text(event.kind) }
                TableColumn("Op") { event in Text(event.op) }
                TableColumn("Ticket") { event in Text(event.ticket == 0 ? "—" : String(event.ticket)) }
                TableColumn("Wait ms") { event in Text(String(format: "%.1f", event.waitMs)) }
                TableColumn("Pending") { event in Text(String(event.pending)) }
                TableColumn("Tag") { event in Text(event.fileTag).font(.caption.monospaced()) }
            }
            if !state.probeJSON.isEmpty {
                Text(state.probeJSON)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
            }
        }
    }
}

struct IdentityPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Identity")
                    .font(.title2.weight(.semibold))
                Text("assert_bound opens a fixture path only as a name, then binds on serial / PARTUUID / FS-UUID. The Mac UI never opens host /dev. Use the example fixture, or your own JSON.")
                    .foregroundStyle(.secondary)
                HStack {
                    Button("Load example") { state.loadExampleIdentity() }
                    Button("Load failing-media example") { state.loadFailingExample() }
                    Button("Scan tree") { state.scanTree() }
                }
                Form {
                    TextField("Manifest", text: $state.identityManifest)
                    TextField("Fixture", text: $state.identityFixture)
                    TextField("Fixture path key", text: $state.identityPath)
                }
                .formStyle(.grouped)
                Button("Bind identity") { state.bindIdentity() }
                if !state.bindJSON.isEmpty {
                    jsonBlock(state.bindJSON)
                }
                if !state.scanJSON.isEmpty {
                    Text("Structural scan")
                        .font(.headline)
                    jsonBlock(state.scanJSON)
                }
                Divider()
                Text("Manifest rotation")
                    .font(.headline)
                Text("Writes a new generation. Refuses overwrite. Dry-run is the default.")
                    .foregroundStyle(.secondary)
                Form {
                    TextField("Old manifest", text: $state.rotateOld)
                    TextField("Observed identity", text: $state.rotateObserved)
                    TextField("Reason", text: $state.rotateReason)
                    TextField("Out (must not exist)", text: $state.rotateOut)
                    TextField("Audit JSONL", text: $state.rotateAudit)
                    Toggle("Dry run", isOn: $state.rotateDryRun)
                }
                .formStyle(.grouped)
                Button("Rotate manifest") { state.rotateManifest() }
            }
        }
    }
}

struct TopologyPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Topology")
                .font(.title2.weight(.semibold))
            Text("Read-only observation of the source directory’s backing disk via df/diskutil. Refused for /Volumes and /dev. This does not bind identity and does not start the queue.")
                .foregroundStyle(.secondary)
            Button("Resolve source topology") { state.runTopology() }
                .disabled(state.source.isEmpty)
            if !state.topologyJSON.isEmpty {
                jsonBlock(state.topologyJSON)
            } else {
                Text("Run this on a Mac after creating a session. Linux hosts will report topology unavailable.")
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct DoctorPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Doctor")
                .font(.title2.weight(.semibold))
            Text("Checks macOS, FUSE-T, the broker binary, and Swift. Does not mount and does not open /dev.")
                .foregroundStyle(.secondary)
            HStack {
                Button("Refresh") { state.refreshDoctor() }
                if state.canMount {
                    Text("Mount possible")
                        .foregroundStyle(Color(red: 36 / 255, green: 88 / 255, blue: 201 / 255))
                } else {
                    Text("Mount not available on this host")
                        .foregroundStyle(.secondary)
                }
            }
            if !state.doctorJSON.isEmpty {
                jsonBlock(state.doctorJSON)
            }
            Text("Install FUSE-T from its official instructions, run make, then make app. Tested runtime: FUSE-T 1.2.7.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

private func jsonBlock(_ text: String) -> some View {
    ScrollView {
        Text(text)
            .font(.system(.caption, design: .monospaced))
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
    .frame(minHeight: 160)
    .padding(8)
    .background(Color(nsColor: .textBackgroundColor), in: RoundedRectangle(cornerRadius: 6))
}
