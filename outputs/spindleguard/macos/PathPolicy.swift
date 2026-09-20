// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

enum PathPolicy {
    static let volumesMessage = "Prototype refuses /Volumes paths. Use disposable directories."
    static let devMessage = "Prototype refuses /dev paths. Use disposable directories."
    static let disjointMessage = "Source and mount must be disjoint."
    static let markerMessage = "Missing disposable test root marker."
    static let prefixMissingMessage = "Write prefix must be an existing safe test directory."
    static let prefixShapeMessage = "Write prefix is invalid."
    static let emptyMessage = "Source and mount paths are required."
    static let markerName = ".spindleguard-test-root"

    static func isVolumes(_ path: String) -> Bool {
        path == "/Volumes" || path.hasPrefix("/Volumes/")
    }

    static func isDev(_ path: String) -> Bool {
        path == "/dev" || path.hasPrefix("/dev/")
    }

    static func resolved(_ path: String) -> String {
        URL(fileURLWithPath: path).resolvingSymlinksInPath().path
    }

    static func forbidden(_ path: String) -> String? {
        if path.isEmpty { return emptyMessage }
        if isVolumes(path) || isVolumes(resolved(path)) { return volumesMessage }
        if isDev(path) || isDev(resolved(path)) { return devMessage }
        return nil
    }

    static func areDisjoint(source: String, mount: String) -> Bool {
        let a = resolved(source)
        let b = resolved(mount)
        if a.isEmpty || b.isEmpty { return false }
        let sourceUnderMount = a.hasPrefix(b) && (a.count == b.count || a.dropFirst(b.count).first == "/")
        let mountUnderSource = b.hasPrefix(a) && (b.count == a.count || b.dropFirst(a.count).first == "/")
        return !sourceUnderMount && !mountUnderSource
    }

    static func writePrefixShape(_ prefix: String) -> Bool {
        guard prefix.count >= 2, prefix.hasPrefix("/") else { return false }
        if prefix.contains("..") { return false }
        if prefix.hasSuffix("/") { return false }
        return true
    }

    static func validate(source: String, mount: String, writePrefix: String?, writable: Bool) -> String? {
        if let err = forbidden(source) { return err }
        if let err = forbidden(mount) { return err }
        if source.isEmpty || mount.isEmpty { return emptyMessage }
        if !areDisjoint(source: source, mount: mount) { return disjointMessage }
        let marker = URL(fileURLWithPath: source).appendingPathComponent(markerName)
        if !FileManager.default.fileExists(atPath: marker.path) {
            return markerMessage
        }
        if writable {
            let prefix = writePrefix ?? ""
            if !writePrefixShape(prefix) { return prefixShapeMessage }
            let dir = URL(fileURLWithPath: source).appendingPathComponent(String(prefix.dropFirst()))
            var isDir: ObjCBool = false
            if !FileManager.default.fileExists(atPath: dir.path, isDirectory: &isDir) || !isDir.boolValue {
                return prefixMissingMessage
            }
        }
        return nil
    }
}
