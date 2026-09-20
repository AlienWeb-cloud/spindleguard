// SPDX-License-Identifier: GPL-2.0-or-later
import AppKit
import Combine
import Foundation

@MainActor
final class AppState: ObservableObject {
    enum Pane: String, CaseIterable, Identifiable, Hashable {
        case broker = "Broker"
        case queue = "Queue"
        case identity = "Identity"
        case topology = "Topology"
        case doctor = "Doctor"
        var id: String { rawValue }
    }

    @Published var pane: Pane = .broker
    @Published var source: String = ""
    @Published var mount: String = ""
    @Published var logPath: String = ""
    @Published var writePrefix: String = "/Workspace"
    @Published var writable: Bool = true
    @Published var delayMs: Double = 150
    @Published var running: Bool = false
    @Published var status: String = "Create a disposable session, then start the broker."
    @Published var error: String = ""
    @Published var events: [BrokerEvent] = []
    @Published var retainedLog: String = ""
    @Published var doctorJSON: String = ""
    @Published var scanJSON: String = ""
    @Published var bindJSON: String = ""
    @Published var topologyJSON: String = ""
    @Published var probeJSON: String = ""
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

    private let broker = BrokerService()
    private var lineBuffer = ""

    init() {
        identityManifest = SGPaths.exampleManifest().path
        identityFixture = SGPaths.exampleFixture().path
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
        runSG(arguments: ["session-create", "--parent", SGPaths.projectRoot().appendingPathComponent("work").path, "--json"]) { data in
            guard let obj = data as? [String: Any] else { return }
            self.source = obj["source"] as? String ?? ""
            self.mount = obj["mount"] as? String ?? ""
            self.logPath = obj["log"] as? String ?? ""
            self.writePrefix = obj["write_prefix"] as? String ?? "/Workspace"
            self.status = "Session retained at \(obj["session"] as? String ?? ""). Files are not deleted."
            self.events = []
            self.retainedLog = ""
            self.pane = .broker
        }
    }

    func start() {
        error = ""
        if let problem = policyProblem {
            error = problem
            return
        }
        if !canMount {
            error = "This Mac cannot mount yet. See Doctor (FUSE-T + make)."
            pane = .doctor
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
            if let obj = data as? [String: Any] {
                self.canMount = obj["can_mount"] as? Bool ?? false
                self.fuseReady = obj["fuse_t_dylib"] as? Bool ?? false
            }
            self.doctorJSON = self.pretty(data)
        }
    }

    func scanTree() {
        runSG(arguments: ["scan", "--root", SGPaths.projectRoot().path, "--json"]) { data in
            self.scanJSON = self.pretty(data)
            self.status = "Structural scan finished."
        }
    }

    func bindIdentity() {
        if let err = PathPolicy.forbidden(identityPath), identityPath.hasPrefix("/Volumes") {
            error = err
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

    private func summarizeProbe() {
        if logPath.isEmpty {
            let evidence = competingWait(from: events)
            probeJSON = pretty(evidence as Any)
            status = evidence["wait_ms"] != nil ? "Queue probe captured a wait." : "Queue probe finished; wait evidence not yet in the log."
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
        }
        if let p = json?["pending"] as? Int {
            pending = p
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
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: SGPaths.python3())
        proc.arguments = [SGPaths.sgCLI().path] + arguments
        proc.currentDirectoryURL = SGPaths.projectRoot()
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = SGPaths.projectRoot().path + ":" + SGPaths.projectRoot().appendingPathComponent("python").path
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
                    self.error = error.localizedDescription
                }
            }
        }
    }
}
