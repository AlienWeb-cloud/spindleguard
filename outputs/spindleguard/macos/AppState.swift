// SPDX-License-Identifier: GPL-2.0-or-later
import AppKit
import Combine
import Foundation
import UniformTypeIdentifiers

struct SetupCheck: Identifiable, Hashable {
    let id: String
    let ok: Bool
    let label: String
    let fix: String
}

struct SessionInfo: Identifiable, Hashable {
    let id: String
    let session: String
    let source: String
    let mount: String
    let log: String
    let bucketed: Bool
}

@MainActor
final class AppState: ObservableObject {
    enum Pane: String, CaseIterable, Identifiable, Hashable {
        case setup = "Setup"
        case broker = "Broker"
        case queue = "Queue"
        case identity = "Identity"
        case retain = "Retain"
        case topology = "Topology"
        case doctor = "Doctor"
        var id: String { rawValue }
    }

    @Published var pane: Pane = .setup
    @Published var source: String = ""
    @Published var mount: String = ""
    @Published var logPath: String = ""
    @Published var sessionRoot: String = ""
    @Published var sessionParentPath: String = ""
    @Published var writePrefix: String = "/Workspace"
    @Published var writable: Bool = true
    @Published var delayMs: Double = 150
    @Published var running: Bool = false
    @Published var busy: Bool = false
    @Published var status: String = "Run Setup, then create a disposable session."
    @Published var error: String = ""
    @Published var events: [BrokerEvent] = []
    @Published var retainedLog: String = ""
    @Published var doctorJSON: String = ""
    @Published var scanJSON: String = ""
    @Published var bindJSON: String = ""
    @Published var topologyJSON: String = ""
    @Published var probeJSON: String = ""
    @Published var setupJSON: String = ""
    @Published var policyJSON: String = ""
    @Published var startPreviewJSON: String = ""
    @Published var verifyJSON: String = ""
    @Published var identityManifest: String = ""
    @Published var identityFixture: String = ""
    @Published var identityPath: String = "/dev/sda1"
    @Published var rotateOld: String = ""
    @Published var rotateObserved: String = ""
    @Published var rotateReason: String = "repartitioned after imaging"
    @Published var rotateOut: String = ""
    @Published var rotateAudit: String = ""
    @Published var rotateDryRun: Bool = true
    @Published var lastWaitMs: Double = 0
    @Published var pending: Int = 0
    @Published var activeOp: String = "idle"
    @Published var fuseReady: Bool = false
    @Published var canMount: Bool = false
    @Published var canBuildApp: Bool = false
    @Published var fuseInstall: String = "brew install macos-fuse-t/homebrew-cask/fuse-t"
    @Published var fuseDocs: String = "https://github.com/macos-fuse-t/fuse-t"
    @Published var nextActions: [String] = []
    @Published var checks: [SetupCheck] = []
    @Published var sessions: [SessionInfo] = []
    @Published var bucket: [SessionInfo] = []
    @Published var sessionBucketed: Bool = false
    @Published var showWizard: Bool = false
    @Published var wizardStep: Int = 0

    static let wizardKey = "SGWizardFinished"
    static let wizardStepCount = 6

    private let broker = BrokerService()
    private var lineBuffer = ""
    private var sgTicket = 0

    init() {
        identityManifest = SGPaths.exampleManifest().path
        identityFixture = SGPaths.exampleFixture().path
        sessionParentPath = SGPaths.sessionParent().path
        broker.onLine = { [weak self] chunk in
            Task { @MainActor in
                self?.ingest(chunk)
            }
        }
        broker.onExit = { [weak self] code in
            Task { @MainActor in
                self?.running = false
                self?.activeOp = "idle"
                if code != 0 && self?.error.isEmpty == true {
                    self?.status = "Broker exited (\(code))."
                } else if code == 0 {
                    self?.status = "Broker stopped."
                }
            }
        }
        refreshDoctor()
        listSessions()
        maybePresentWizard()
    }

    var policyProblem: String? {
        PathPolicy.validate(
            source: source,
            mount: mount,
            writePrefix: writable ? writePrefix : nil,
            writable: writable
        )
    }

    func chooseDirectory(title: String, setter: @escaping (String) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true
        panel.message = title
        panel.directoryURL = FileManager.default.homeDirectoryForCurrentUser
        beginPanel(panel, setter: setter)
    }

    func chooseJSONFile(title: String, setter: @escaping (String) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.json]
        panel.message = title
        beginPanel(panel, setter: setter)
    }

    func chooseSaveJSON(title: String, setter: @escaping (String) -> Void) {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.json]
        panel.canCreateDirectories = true
        panel.message = title
        panel.nameFieldStringValue = "manifest.generation-2.json"
        panel.begin { response in
            guard response == .OK, let url = panel.url else { return }
            Task { @MainActor in
                if FileManager.default.fileExists(atPath: url.path) {
                    self.error = "refuses to overwrite existing manifest path"
                    return
                }
                if let err = PathPolicy.forbidden(url.path) {
                    self.error = err
                    return
                }
                setter(url.path)
                self.error = ""
            }
        }
    }

    private func beginPanel(_ panel: NSOpenPanel, setter: @escaping (String) -> Void) {
        panel.begin { response in
            guard response == .OK, let url = panel.url else { return }
            Task { @MainActor in
                if let err = PathPolicy.forbidden(url.path) {
                    self.error = err
                    return
                }
                setter(url.path)
                self.error = ""
            }
        }
    }

    func newSession() {
        error = ""
        let parent = sessionParentPath.isEmpty ? SGPaths.sessionParent().path : sessionParentPath
        if let err = PathPolicy.forbidden(parent) {
            error = err
            pane = .setup
            return
        }
        runSG(arguments: ["session-create", "--parent", parent, "--json"]) { data in
            guard let obj = data as? [String: Any] else { return }
            self.applySession(obj)
            self.status = "Session retained at \(obj["session"] as? String ?? ""). Move it to the bucket when you want to purge."
            self.events = []
            self.retainedLog = ""
            self.listSessions()
            self.pane = .broker
        }
    }

    func loadSession() {
        error = ""
        chooseJSONFile(title: "Load session.json") { path in
            self.runSG(arguments: ["session-load", "--file", path, "--json"]) { data in
                guard let obj = data as? [String: Any] else { return }
                self.applySession(obj)
                self.status = obj["deletion_bucket"] as? Bool == true
                    ? "Loaded from the deletion bucket. Restore before Start, or purge to delete."
                    : "Loaded retained session. Move it to the bucket when you want to purge."
                self.pane = .broker
            }
        }
    }

    func listSessions() {
        let parent = sessionParentPath.isEmpty ? SGPaths.sessionParent().path : sessionParentPath
        if let err = PathPolicy.forbidden(parent) {
            error = err
            return
        }
        runSG(arguments: ["session-list", "--parent", parent, "--json"]) { data in
            guard let obj = data as? [String: Any] else { return }
            self.sessions = self.parseSessions(obj["sessions"] as? [[String: Any]] ?? [])
            self.bucket = self.parseSessions(obj["bucket"] as? [[String: Any]] ?? [])
        }
    }

    private func parseSessions(_ raw: [[String: Any]]) -> [SessionInfo] {
        raw.compactMap { item in
            guard let session = item["session"] as? String else { return nil }
            return SessionInfo(
                id: session,
                session: session,
                source: item["source"] as? String ?? "",
                mount: item["mount"] as? String ?? "",
                log: item["log"] as? String ?? "",
                bucketed: item["deletion_bucket"] as? Bool ?? false
            )
        }
    }

    func loadListedSession(_ row: SessionInfo) {
        error = ""
        let file = URL(fileURLWithPath: row.session).appendingPathComponent("session.json").path
        runSG(arguments: ["session-load", "--file", file, "--json"]) { data in
            guard let obj = data as? [String: Any] else { return }
            self.applySession(obj)
            self.status = obj["deletion_bucket"] as? Bool == true
                ? "Loaded from the deletion bucket. Restore before Start, or purge to delete."
                : "Loaded retained session. Move it to the bucket when you want to purge."
            self.pane = .broker
        }
    }

    private func sessionParent() -> String {
        sessionParentPath.isEmpty ? SGPaths.sessionParent().path : sessionParentPath
    }

    private func clearIfCurrent(session: String) {
        if sessionRoot == session || source.hasPrefix(session + "/") || source == session {
            source = ""
            mount = ""
            logPath = ""
            sessionRoot = ""
            sessionBucketed = false
        }
    }

    func bucketSession(_ row: SessionInfo) {
        error = ""
        if running {
            error = "Stop the broker before moving this session to the bucket."
            pane = .broker
            return
        }
        if row.bucketed {
            error = "Session is already in the bucket."
            pane = .retain
            return
        }
        let parent = sessionParent()
        if let err = PathPolicy.forbidden(parent) ?? PathPolicy.forbidden(row.session) {
            error = err
            return
        }
        runSG(arguments: ["session-bucket", "--session", row.session, "--parent", parent, "--json"]) { data in
            self.status = "Moved to the deletion bucket. Restore or purge from Retain."
            self.clearIfCurrent(session: row.session)
            if let obj = data as? [String: Any], let moved = obj["session"] as? String {
                self.sessionRoot = moved
                self.sessionBucketed = true
                self.source = obj["source"] as? String ?? ""
                self.mount = obj["mount"] as? String ?? ""
                self.logPath = obj["log"] as? String ?? ""
            }
            self.listSessions()
            self.pane = .retain
        }
    }

    func bucketCurrentSession() {
        revealPane(.retain)
        if sessionRoot.isEmpty {
            error = "Create or load a session first."
            return
        }
        bucketSession(
            SessionInfo(
                id: sessionRoot,
                session: sessionRoot,
                source: source,
                mount: mount,
                log: logPath,
                bucketed: sessionBucketed
            )
        )
    }

    func restoreSession(_ row: SessionInfo) {
        error = ""
        if !row.bucketed {
            error = "Session is not in the bucket."
            pane = .retain
            return
        }
        let parent = sessionParent()
        if let err = PathPolicy.forbidden(parent) ?? PathPolicy.forbidden(row.session) {
            error = err
            return
        }
        runSG(arguments: ["session-restore", "--session", row.session, "--parent", parent, "--json"]) { data in
            guard let obj = data as? [String: Any] else { return }
            self.applySession(obj)
            self.status = "Restored from the deletion bucket."
            self.listSessions()
            self.pane = .broker
        }
    }

    func purgeSession(_ row: SessionInfo) {
        error = ""
        if !row.bucketed {
            error = "Move the session to the bucket before purging."
            pane = .retain
            return
        }
        if running && (sessionRoot == row.session || source.hasPrefix(row.session + "/")) {
            error = "Stop the broker before purging this session."
            pane = .broker
            return
        }
        let alert = NSAlert()
        alert.messageText = "Permanently delete this bucketed session?"
        alert.informativeText = "\(row.session)\n\nThis cannot be undone. Only ui-session directories in the deletion bucket are deleted."
        alert.addButton(withTitle: "Purge")
        alert.addButton(withTitle: "Cancel")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        let parent = sessionParent()
        runSG(arguments: ["session-purge", "--session", row.session, "--parent", parent, "--yes", "--json"]) { _ in
            self.status = "Purged from the deletion bucket."
            self.clearIfCurrent(session: row.session)
            self.listSessions()
            self.pane = .retain
        }
    }

    func purgeBucket() {
        error = ""
        revealPane(.retain)
        if running {
            error = "Stop the broker before emptying the bucket."
            return
        }
        let alert = NSAlert()
        alert.messageText = "Permanently delete every session in the bucket?"
        alert.informativeText = "Only ui-session directories already in the deletion bucket are removed. Active sessions are not deleted."
        alert.addButton(withTitle: "Empty bucket")
        alert.addButton(withTitle: "Cancel")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        let parent = sessionParent()
        runSG(arguments: ["session-purge", "--all", "--parent", parent, "--yes", "--json"]) { data in
            if let obj = data as? [String: Any], let count = obj["count"] as? Int {
                self.status = "Purged \(count) session(s) from the bucket."
            } else {
                self.status = "Bucket emptied."
            }
            if self.sessionBucketed {
                self.clearIfCurrent(session: self.sessionRoot)
            }
            self.listSessions()
        }
    }

    func showMainWindow() {
        NSApplication.shared.activate(ignoringOtherApps: true)
        if let window = NSApplication.shared.windows.first(where: { $0.canBecomeMain }) {
            window.makeKeyAndOrderFront(nil)
        }
    }

    func revealPane(_ pane: Pane) {
        showMainWindow()
        self.pane = pane
    }

    func maybePresentWizard() {
        if !UserDefaults.standard.bool(forKey: Self.wizardKey) {
            wizardStep = 0
            showWizard = true
        }
    }

    func openWizard() {
        wizardStep = 0
        showWizard = true
        showMainWindow()
    }

    func wizardBack() {
        if wizardStep > 0 { wizardStep -= 1 }
    }

    func wizardNext() {
        if wizardStep < Self.wizardStepCount - 1 { wizardStep += 1 }
    }

    func finishWizard(skipped: Bool) {
        UserDefaults.standard.set(true, forKey: Self.wizardKey)
        showWizard = false
        if skipped || source.isEmpty {
            pane = .setup
            status = skipped ? "Wizard skipped. Use Setup whenever you want." : "Wizard finished. Create a session from Setup when you are ready."
        } else {
            pane = .broker
            status = "Wizard finished. Session is retained. Start when this Mac can mount."
        }
    }

    func start() {
        error = ""
        if sessionBucketed {
            error = "Restore this session from the bucket before starting."
            pane = .retain
            return
        }
        if let problem = policyProblem {
            error = problem
            pane = .broker
            return
        }
        if !canMount {
            error = "This Mac cannot mount yet. Finish Setup (FUSE-T + broker)."
            pane = .setup
            return
        }
        do {
            try broker.start(
                binary: SGPaths.brokerBinary(),
                source: source,
                mount: mount,
                writePrefix: writable ? writePrefix : nil,
                delayMs: Int(delayMs)
            )
            running = true
            status = "Broker starting. Open the mount in Finder when it appears."
            pane = .queue
        } catch {
            self.error = error.localizedDescription
        }
    }

    func stop() {
        broker.stop(mount: mount)
        running = false
        activeOp = "idle"
        status = "Stop requested. Mount should unmount; session files are retained."
    }

    func unmountOnly() {
        error = ""
        if mount.isEmpty {
            error = "Mount path is required."
            pane = .broker
            return
        }
        runSG(arguments: ["unmount", "--mount", mount, "--json"]) { data in
            self.status = "Unmount requested."
            self.policyJSON = self.pretty(data)
        }
    }

    func openMount() {
        guard PathPolicy.forbidden(mount) == nil else {
            error = PathPolicy.volumesMessage
            return
        }
        NSWorkspace.shared.open(URL(fileURLWithPath: mount))
    }

    func openSource() {
        guard PathPolicy.forbidden(source) == nil else {
            error = PathPolicy.volumesMessage
            return
        }
        NSWorkspace.shared.open(URL(fileURLWithPath: source))
    }

    func revealLog() {
        guard !logPath.isEmpty, PathPolicy.forbidden(logPath) == nil else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: logPath)])
    }

    func openSessionParent() {
        let parent = sessionParentPath.isEmpty ? SGPaths.sessionParent().path : sessionParentPath
        guard PathPolicy.forbidden(parent) == nil else {
            error = PathPolicy.volumesMessage
            return
        }
        NSWorkspace.shared.open(URL(fileURLWithPath: parent))
    }

    func probeQueue() {
        error = ""
        let mountURL = URL(fileURLWithPath: mount)
        let large = mountURL.appendingPathComponent("large.bin")
        let second = mountURL.appendingPathComponent("second.txt")
        status = "Probing queue: two concurrent reads through the mount."
        DispatchQueue.global(qos: .userInitiated).async {
            let group = DispatchGroup()
            group.enter()
            DispatchQueue.global().async {
                _ = try? Data(contentsOf: large)
                group.leave()
            }
            group.enter()
            DispatchQueue.global().async {
                Thread.sleep(forTimeInterval: 0.05)
                _ = try? Data(contentsOf: second)
                group.leave()
            }
            group.wait()
            DispatchQueue.main.async {
                self.summarizeProbe()
            }
        }
    }

    func refreshDoctor() {
        runSG(arguments: ["doctor", "--json"]) { data in
            self.applyDoctor(data)
            self.doctorJSON = self.pretty(data)
        }
    }

    func previewSetup() {
        error = ""
        runSG(arguments: ["setup", "--dry-run", "--json"]) { data in
            self.setupJSON = self.pretty(data)
            self.status = "Setup preview only. Run Setup to build on this Mac."
            self.refreshDoctor()
        }
    }

    func runSetup() {
        error = ""
        runSG(arguments: ["setup", "--json"]) { data in
            self.setupJSON = self.pretty(data)
            if let obj = data as? [String: Any] {
                let ok = obj["ok"] as? Bool ?? false
                self.status = ok
                    ? "Setup finished. Create a session if the broker is ready."
                    : "Setup reported problems. See the JSON below."
            } else {
                self.status = "Setup finished."
            }
            self.refreshDoctor()
        }
    }

    func installFuse() {
        error = ""
        let alert = NSAlert()
        alert.messageText = "Install FUSE-T with Homebrew?"
        alert.informativeText = """
        \(fuseInstall)

        This is a system package with a separate license. SpindleGuard will not install it unless you confirm. Official docs: \(fuseDocs)
        """
        alert.addButton(withTitle: "Install")
        alert.addButton(withTitle: "Copy command")
        alert.addButton(withTitle: "Cancel")
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            runSG(arguments: ["setup", "--install-fuse", "--yes", "--json"]) { data in
                self.setupJSON = self.pretty(data)
                self.status = "FUSE-T install finished. Run Setup to build the broker."
                self.refreshDoctor()
            }
        case .alertSecondButtonReturn:
            copyFuseCommand()
        default:
            break
        }
    }

    func copyFuseCommand() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(fuseInstall, forType: .string)
        status = "Copied: \(fuseInstall)"
    }

    func openFuseDocs() {
        guard let url = URL(string: fuseDocs) else { return }
        NSWorkspace.shared.open(url)
    }

    func policyCheck() {
        var args = ["policy-check", "--source", source, "--mount", mount, "--json"]
        if writable {
            args += ["--write-prefix", writePrefix]
        }
        runSG(arguments: args) { data in
            self.policyJSON = self.pretty(data)
            self.status = "Policy check finished."
        }
    }

    func previewStart() {
        var args = [
            "start", "--dry-run", "--json",
            "--source", source,
            "--mount", mount,
            "--delay-ms", String(Int(delayMs)),
            "--binary", SGPaths.brokerBinary().path,
        ]
        if writable {
            args += ["--write-prefix", writePrefix]
        }
        runSG(arguments: args) { data in
            self.startPreviewJSON = self.pretty(data)
            self.status = "Start preview (no mount)."
        }
    }

    func verifyInstall() {
        error = ""
        runSG(arguments: ["verify", "--quick", "--json"]) { data in
            self.verifyJSON = self.pretty(data)
            if let obj = data as? [String: Any], let ok = obj["ok"] as? Bool {
                self.status = ok ? "Install verification passed." : "Install verification found failures."
            } else {
                self.status = "Install verification finished."
            }
        }
    }

    func scanTree() {
        runSG(arguments: ["scan", "--root", SGPaths.projectRoot().path, "--json"]) { data in
            self.scanJSON = self.pretty(data)
            self.status = "Structural scan finished."
        }
    }

    func bindIdentity() {
        if identityPath.hasPrefix("/Volumes") {
            error = PathPolicy.volumesMessage
            return
        }
        runSG(arguments: [
            "bind",
            "--manifest", identityManifest,
            "--path", identityPath,
            "--fixture", identityFixture,
        ], raw: true) { data in
            self.bindJSON = self.pretty(data)
            self.status = "Identity bind finished (fixture; no host /dev open)."
        }
    }

    func rotateManifest() {
        var args = [
            "rotate-manifest",
            "--old", rotateOld,
            "--observed", rotateObserved,
            "--reason", rotateReason,
            "--out", rotateOut,
            "--audit", rotateAudit,
        ]
        if rotateDryRun { args.append("--dry-run") }
        runSG(arguments: args, raw: true) { data in
            self.bindJSON = self.pretty(data)
            self.status = self.rotateDryRun ? "Rotation dry-run only." : "New manifest generation written."
        }
    }

    func runTopology() {
        if let err = PathPolicy.forbidden(source) {
            error = err
            return
        }
        runSG(arguments: ["topology", "--path", source], raw: true) { data in
            self.topologyJSON = self.pretty(data)
            self.status = "Topology helper finished."
        }
    }

    func loadExampleIdentity() {
        identityManifest = SGPaths.exampleManifest().path
        identityFixture = SGPaths.exampleFixture().path
        identityPath = "/dev/sda1"
        status = "Loaded example fixture. Bind does not open host /dev."
    }

    func loadFailingExample() {
        identityManifest = SGPaths.exampleFailingManifest().path
        identityFixture = SGPaths.exampleFixture().path
        status = "Loaded failing-media example. Fingerprint should be skipped."
    }

    private func applySession(_ obj: [String: Any]) {
        source = obj["source"] as? String ?? ""
        mount = obj["mount"] as? String ?? ""
        logPath = obj["log"] as? String ?? ""
        sessionRoot = obj["session"] as? String ?? ""
        writePrefix = obj["write_prefix"] as? String ?? "/Workspace"
        sessionBucketed = obj["deletion_bucket"] as? Bool ?? false
        error = ""
    }

    private func applyDoctor(_ data: Any) {
        guard let obj = data as? [String: Any] else { return }
        canMount = obj["can_mount"] as? Bool ?? false
        canBuildApp = obj["can_build_app"] as? Bool ?? false
        fuseReady = obj["fuse_t_dylib"] as? Bool ?? false
        fuseInstall = obj["fuse_install"] as? String ?? fuseInstall
        fuseDocs = obj["fuse_docs"] as? String ?? fuseDocs
        nextActions = obj["next"] as? [String] ?? []
        if let raw = obj["checks"] as? [[String: Any]] {
            checks = raw.compactMap { item in
                guard let id = item["id"] as? String, let label = item["label"] as? String else { return nil }
                return SetupCheck(
                    id: id,
                    ok: item["ok"] as? Bool ?? false,
                    label: label,
                    fix: item["fix"] as? String ?? ""
                )
            }
        }
    }

    private func summarizeProbe() {
        if logPath.isEmpty {
            let evidence = competingWait(from: events)
            probeJSON = pretty(evidence as Any)
            status = evidence["wait_ms"] is NSNull ? "Queue probe finished; wait evidence not yet in the log." : "Queue probe captured a wait."
            return
        }
        runSG(arguments: ["probe-log", "--log", logPath, "--json"]) { data in
            self.probeJSON = self.pretty(data)
            self.status = "Queue probe compared against the retained log."
        }
    }

    private func ingest(_ chunk: String) {
        lineBuffer += chunk
        var parts = lineBuffer.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        lineBuffer = parts.popLast() ?? ""
        for line in parts {
            appendLine(line)
        }
    }

    private func appendLine(_ line: String) {
        guard !line.isEmpty else { return }
        retainedLog += line + "\n"
        if !logPath.isEmpty, PathPolicy.forbidden(logPath) == nil {
            if let handle = FileHandle(forWritingAtPath: logPath) {
                handle.seekToEndOfFile()
                if let data = (line + "\n").data(using: .utf8) {
                    handle.write(data)
                }
                try? handle.close()
            }
        }
        var json: [String: Any]?
        if line.first == "{", let data = line.data(using: .utf8) {
            json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        }
        let event = BrokerEvent(raw: line, json: json)
        events.append(event)
        if events.count > 2000 {
            events.removeFirst(events.count - 2000)
        }
        if let wait = json?["wait_ms"] as? Double, wait > lastWaitMs {
            lastWaitMs = wait
        } else if let n = json?["wait_ms"] as? NSNumber, n.doubleValue > lastWaitMs {
            lastWaitMs = n.doubleValue
        }
        if let p = json?["pending"] as? Int {
            pending = p
        } else if let n = json?["pending"] as? NSNumber {
            pending = n.intValue
        }
        if json?["event"] as? String == "start" {
            activeOp = json?["op"] as? String ?? "active"
        }
        if json?["event"] as? String == "finish" {
            activeOp = "idle"
        }
    }

    private func competingWait(from events: [BrokerEvent]) -> [String: Any] {
        var start: [Int: BrokerEvent] = [:]
        var finish: [Int: BrokerEvent] = [:]
        var active: [Int] = []
        var pairs: [(Int, Int)] = []
        for event in events {
            let t = event.ticket
            switch event.kind {
            case "queued":
                if let current = active.first {
                    pairs.append((current, t))
                }
            case "start":
                start[t] = event
                active.append(t)
            case "finish":
                finish[t] = event
                active.removeAll { $0 == t }
            default:
                break
            }
        }
        for (a, b) in pairs {
            if let wait = start[b]?.waitMs, wait > 20 {
                return ["active_ticket": a, "queued_ticket": b, "wait_ms": wait]
            }
        }
        return ["wait_ms": NSNull()]
    }

    private func pretty(_ data: Any) -> String {
        if let text = data as? String { return text }
        guard JSONSerialization.isValidJSONObject(data),
              let raw = try? JSONSerialization.data(withJSONObject: data, options: [.prettyPrinted, .sortedKeys]),
              let text = String(data: raw, encoding: .utf8)
        else {
            return String(describing: data)
        }
        return text
    }

    private func runSG(arguments: [String], raw: Bool = false, done: @escaping (Any) -> Void) {
        sgTicket += 1
        let ticket = sgTicket
        busy = true
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: SGPaths.python3())
        proc.arguments = [SGPaths.sgCLI().path] + arguments
        proc.currentDirectoryURL = SGPaths.projectRoot()
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = SGPaths.projectRoot().path + ":" + SGPaths.projectRoot().appendingPathComponent("python").path
        env["SPINDLEGUARD_ROOT"] = SGPaths.projectRoot().path
        env["SPINDLEGUARD_SESSION_PARENT"] = sessionParentPath.isEmpty ? SGPaths.sessionParent().path : sessionParentPath
        proc.environment = env
        let out = Pipe()
        let err = Pipe()
        proc.standardOutput = out
        proc.standardError = err
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try proc.run()
                proc.waitUntilExit()
                let stdout = String(data: out.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let stderr = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                DispatchQueue.main.async {
                    if ticket == self.sgTicket {
                        self.busy = false
                    }
                    let errText = stderr.trimmingCharacters(in: .whitespacesAndNewlines)
                    if proc.terminationStatus != 0 && !errText.isEmpty {
                        self.error = errText
                    } else if !errText.isEmpty {
                        self.status = errText
                    }
                    if raw {
                        done(stdout.isEmpty ? stderr : stdout)
                        return
                    }
                    if let data = stdout.data(using: .utf8),
                       let obj = try? JSONSerialization.jsonObject(with: data) {
                        done(obj)
                    } else {
                        done(stdout)
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    if ticket == self.sgTicket {
                        self.busy = false
                    }
                    self.error = error.localizedDescription
                }
            }
        }
    }
}
