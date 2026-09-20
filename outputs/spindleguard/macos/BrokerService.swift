// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

struct BrokerEvent: Identifiable, Equatable {
    let id = UUID()
    let raw: String
    let json: [String: Any]?

    var kind: String { json?["event"] as? String ?? "note" }
    var op: String { json?["op"] as? String ?? "" }
    var ticket: Int {
        if let i = json?["ticket"] as? Int { return i }
        if let n = json?["ticket"] as? NSNumber { return n.intValue }
        return 0
    }
    var waitMs: Double {
        if let d = json?["wait_ms"] as? Double { return d }
        if let n = json?["wait_ms"] as? NSNumber { return n.doubleValue }
        return 0
    }
    var pending: Int {
        if let i = json?["pending"] as? Int { return i }
        if let n = json?["pending"] as? NSNumber { return n.intValue }
        return 0
    }
    var fileTag: String { json?["file_tag"] as? String ?? "" }

    static func == (lhs: BrokerEvent, rhs: BrokerEvent) -> Bool {
        lhs.id == rhs.id
    }
}

final class BrokerService {
    private var process: Process?
    private var stderr: Pipe?
    var onLine: ((String) -> Void)?
    var onExit: ((Int32) -> Void)?

    var isRunning: Bool { process?.isRunning == true }

    func start(binary: URL, source: String, mount: String, writePrefix: String?, delayMs: Int) throws {
        if let err = PathPolicy.validate(
            source: source,
            mount: mount,
            writePrefix: writePrefix,
            writable: writePrefix != nil
        ) {
            throw NSError(domain: "SpindleGuard", code: 2, userInfo: [NSLocalizedDescriptionKey: err])
        }
        var args = [source, mount]
        let writable = writePrefix != nil
        if writable || delayMs > 0 {
            args.append(writable ? writePrefix! : "-")
        }
        if delayMs > 0 {
            args.append(String(delayMs))
        }
        let proc = Process()
        proc.executableURL = binary
        proc.arguments = args
        proc.currentDirectoryURL = SGPaths.projectRoot()
        let pipe = Pipe()
        proc.standardError = pipe
        proc.standardOutput = pipe
        proc.terminationHandler = { [weak self] finished in
            DispatchQueue.main.async {
                self?.onExit?(finished.terminationStatus)
            }
        }
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let chunk = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                self?.onLine?(chunk)
            }
        }
        try proc.run()
        process = proc
        stderr = pipe
    }

    func unmount(mount: String) {
        if !mount.isEmpty, PathPolicy.forbidden(mount) == nil {
            let umount = Process()
            umount.executableURL = URL(fileURLWithPath: "/sbin/umount")
            umount.arguments = [mount]
            try? umount.run()
            umount.waitUntilExit()
        }
    }

    func stop(mount: String) {
        unmount(mount: mount)
        process?.terminate()
        process?.waitUntilExit()
        stderr?.fileHandleForReading.readabilityHandler = nil
        process = nil
        stderr = nil
    }
}
