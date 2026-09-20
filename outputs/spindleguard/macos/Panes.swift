// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI

struct SetupPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Setup")
                    .font(.title2.weight(.semibold))
                Text("One-command install on a Mac: FUSE-T (confirmed Homebrew only), then the broker and this app. Nothing here mounts, opens /dev, or deletes files.")
                    .foregroundStyle(.secondary)
                Button("First-run wizard…") { state.openWizard() }
                    .disabled(state.busy)
                CheckList(checks: state.checks)
                if !state.nextActions.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Next")
                            .font(.headline)
                        ForEach(Array(state.nextActions.enumerated()), id: \.offset) { _, item in
                            Text("• \(item)")
                                .font(.callout.monospaced())
                        }
                    }
                }
                HStack {
                    Button("Preview setup") { state.previewSetup() }
                    Button("Run setup") { state.runSetup() }
                        .keyboardShortcut("s", modifiers: [.command, .shift])
                    Button("Verify install") { state.verifyInstall() }
                    Button("Refresh doctor") { state.refreshDoctor() }
                }
                .disabled(state.busy)
                HStack {
                    Button("Install FUSE-T…") { state.installFuse() }
                    Button("Copy FUSE-T command") { state.copyFuseCommand() }
                    Button("Open FUSE-T docs") { state.openFuseDocs() }
                }
                .disabled(state.busy)
                Form {
                    LabeledContent("Session parent") {
                        HStack {
                            TextField("Session parent", text: $state.sessionParentPath)
                            Button("Choose…") {
                                state.chooseDirectory(title: "Choose session parent") { state.sessionParentPath = $0 }
                            }
                            Button("Open") { state.openSessionParent() }
                                .disabled(state.sessionParentPath.isEmpty)
                        }
                    }
                }
                .formStyle(.grouped)
                HStack {
                    Button("New disposable session") { state.newSession() }
                    Button("Load session…") { state.loadSession() }
                    Spacer()
                    if state.canMount {
                        Text("Ready to mount")
                            .foregroundStyle(Color(red: 36 / 255, green: 88 / 255, blue: 201 / 255))
                    } else {
                        Text("Mount not available on this host")
                            .foregroundStyle(.secondary)
                    }
                }
                .disabled(state.busy)
                statusBlock
                if !state.setupJSON.isEmpty {
                    Text("Setup report")
                        .font(.headline)
                    jsonBlock(state.setupJSON)
                }
                if !state.verifyJSON.isEmpty {
                    Text("Verify report")
                        .font(.headline)
                    jsonBlock(state.verifyJSON)
                }
            }
        }
    }

    private var statusBlock: some View {
        StatusBanner()
    }
}

struct BrokerPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Broker")
                    .font(.title2.weight(.semibold))
                Text("Disposable test data only. The prototype refuses /Volumes and /dev, requires a .spindleguard-test-root marker, and serializes backing work through one FIFO queue.")
                    .foregroundStyle(.secondary)
                HStack {
                    Button("New session") { state.newSession() }
                    Button("Load session…") { state.loadSession() }
                    Button(state.running ? "Stop" : "Start") {
                        state.running ? state.stop() : state.start()
                    }
                    .disabled(!state.running && (state.sessionBucketed || state.sessionPurged))
                    Button("Unmount") { state.unmountOnly() }
                        .disabled(state.mount.isEmpty)
                    Button("Policy check") { state.policyCheck() }
                    Button("Preview start") { state.previewStart() }
                        .disabled(state.sessionBucketed || state.sessionPurged)
                }
                .disabled(state.busy)
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
                    LabeledContent("Log") {
                        HStack {
                            TextField("broker.jsonl", text: $state.logPath)
                            Button("Reveal") { state.revealLog() }
                                .disabled(state.logPath.isEmpty)
                        }
                    }
                }
                .formStyle(.grouped)
                HStack {
                    Button("Open Source") { state.openSource() }
                        .disabled(state.source.isEmpty)
                    Button("Open Mount") { state.openMount() }
                        .disabled(state.mount.isEmpty)
                    Button("Reveal log") { state.revealLog() }
                        .disabled(state.logPath.isEmpty)
                    Spacer()
                }
                StatusBanner()
                if !state.policyJSON.isEmpty {
                    Text("Policy")
                        .font(.headline)
                    jsonBlock(state.policyJSON)
                }
                if !state.startPreviewJSON.isEmpty {
                    Text("Start preview")
                        .font(.headline)
                    jsonBlock(state.startPreviewJSON)
                }
            }
        }
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
                    .disabled(!state.running || state.busy)
                Button("Reveal log") { state.revealLog() }
                    .disabled(state.logPath.isEmpty)
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
                    Button("Bind identity") { state.bindIdentity() }
                }
                .disabled(state.busy)
                Form {
                    LabeledContent("Manifest") {
                        HStack {
                            TextField("Manifest", text: $state.identityManifest)
                            Button("Choose…") {
                                state.chooseJSONFile(title: "Choose manifest") { state.identityManifest = $0 }
                            }
                        }
                    }
                    LabeledContent("Fixture") {
                        HStack {
                            TextField("Fixture", text: $state.identityFixture)
                            Button("Choose…") {
                                state.chooseJSONFile(title: "Choose fixture") { state.identityFixture = $0 }
                            }
                        }
                    }
                    TextField("Fixture path key", text: $state.identityPath)
                }
                .formStyle(.grouped)
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
                    LabeledContent("Old manifest") {
                        HStack {
                            TextField("Old manifest", text: $state.rotateOld)
                            Button("Choose…") {
                                state.chooseJSONFile(title: "Old manifest") { state.rotateOld = $0 }
                            }
                        }
                    }
                    LabeledContent("Observed identity") {
                        HStack {
                            TextField("Observed identity", text: $state.rotateObserved)
                            Button("Choose…") {
                                state.chooseJSONFile(title: "Observed identity") { state.rotateObserved = $0 }
                            }
                        }
                    }
                    TextField("Reason", text: $state.rotateReason)
                    LabeledContent("Out (must not exist)") {
                        HStack {
                            TextField("Out", text: $state.rotateOut)
                            Button("Choose…") {
                                state.chooseSaveJSON(title: "New manifest path") { state.rotateOut = $0 }
                            }
                        }
                    }
                    LabeledContent("Audit JSONL") {
                        HStack {
                            TextField("Audit JSONL", text: $state.rotateAudit)
                            Button("Choose…") {
                                state.chooseSaveJSON(title: "Audit JSONL") { state.rotateAudit = $0 }
                            }
                        }
                    }
                    Toggle("Dry run", isOn: $state.rotateDryRun)
                }
                .formStyle(.grouped)
                Button("Rotate manifest") { state.rotateManifest() }
                    .disabled(state.busy)
            }
        }
    }
}

struct RetainPane: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Retain")
                    .font(.title2.weight(.semibold))
                Text("Three lists. Active is usable. Bucket is recycle. Purged still has files until you destroy them. Destroy only deletes ui-session directories already in the purged list, after confirm. /Volumes and /dev are refused.")
                    .foregroundStyle(.secondary)
                HStack {
                    Button("Refresh list") { state.listSessions() }
                    Button("New session") { state.newSession() }
                    Button("Move current to bucket") { state.bucketCurrentSession() }
                        .disabled(state.sessionRoot.isEmpty || state.sessionBucketed || state.sessionPurged)
                    Button("Purge bucket") { state.purgeBucket() }
                        .disabled(state.bucket.isEmpty)
                    Button("Empty purged…") { state.destroyPurged() }
                        .disabled(state.purged.isEmpty)
                    Button("Open parent") { state.openSessionParent() }
                        .disabled(state.sessionParentPath.isEmpty)
                }
                .disabled(state.busy)
                listBlock("Active", rows: state.sessions, empty: "No active sessions in this parent yet.") { row in
                    HStack {
                        Button("Load") { state.loadListedSession(row) }
                        Button("Bucket") { state.bucketSession(row) }
                    }
                }
                listBlock("Bucket", rows: state.bucket, empty: "Bucket is empty.") { row in
                    HStack {
                        Button("Load") { state.loadListedSession(row) }
                        Button("Restore") { state.restoreSession(row) }
                        Button("Purge") { state.purgeSession(row) }
                    }
                }
                listBlock("Purged", rows: state.purged, empty: "Purged list is empty.") { row in
                    HStack {
                        Button("Load") { state.loadListedSession(row) }
                        Button("Restore") { state.restoreSession(row) }
                        Button("Destroy…") { state.destroySession(row) }
                    }
                }
                StatusBanner()
            }
        }
        .onAppear { state.listSessions() }
    }

    private func listBlock<Actions: View>(
        _ title: String,
        rows: [SessionInfo],
        empty: String,
        @ViewBuilder actions: @escaping (SessionInfo) -> Actions
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            if rows.isEmpty {
                Text(empty)
                    .foregroundStyle(.secondary)
            } else {
                Table(rows) {
                    TableColumn("Session") { row in Text(row.session).font(.caption.monospaced()) }
                    TableColumn("Source") { row in Text(row.source).font(.caption.monospaced()) }
                    TableColumn("") { row in actions(row) }
                }
                .frame(minHeight: 88)
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
                .disabled(state.source.isEmpty || state.busy)
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
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Doctor")
                    .font(.title2.weight(.semibold))
                Text("Checks macOS, FUSE-T, the broker binary, and Swift. Does not mount and does not open /dev.")
                    .foregroundStyle(.secondary)
                HStack {
                    Button("Refresh") { state.refreshDoctor() }
                    Button("Run setup") { state.runSetup() }
                    Button("Verify install") { state.verifyInstall() }
                    Button("Copy FUSE-T command") { state.copyFuseCommand() }
                    if state.canMount {
                        Text("Mount possible")
                            .foregroundStyle(Color(red: 36 / 255, green: 88 / 255, blue: 201 / 255))
                    } else {
                        Text("Mount not available on this host")
                            .foregroundStyle(.secondary)
                    }
                }
                .disabled(state.busy)
                CheckList(checks: state.checks)
                if !state.doctorJSON.isEmpty {
                    jsonBlock(state.doctorJSON)
                }
                if !state.verifyJSON.isEmpty {
                    Text("Verify report")
                        .font(.headline)
                    jsonBlock(state.verifyJSON)
                }
                Text("Install FUSE-T from its official instructions, then Run Setup. Tested runtime: FUSE-T 1.2.7. Homebrew install is never automatic.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct CheckList: View {
    let checks: [SetupCheck]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(checks) { check in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: check.ok ? "checkmark.circle.fill" : "xmark.circle")
                        .foregroundStyle(check.ok ? Color(red: 36 / 255, green: 88 / 255, blue: 201 / 255) : Color.secondary)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(check.label)
                        if !check.ok && !check.fix.isEmpty {
                            Text(check.fix)
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                    }
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
    }
}

struct StatusBanner: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(state.status)
            if !state.error.isEmpty {
                Text(state.error)
                    .foregroundStyle(.red)
                    .textSelection(.enabled)
            }
            Text("Active → bucket → purged. Destroy only from the purged list, with confirm.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
    }
}

func jsonBlock(_ text: String) -> some View {
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
