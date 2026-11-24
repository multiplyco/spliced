import AppKit

/// What the app remembers about projects: the recent ones, which were open at quit, and each one's port.
/// A project keeps its port, because the app's own memory in a page (the welcome seen, a hidden explainer, the theme)
/// is kept per address: a new port every launch would make every project start over.
enum Projects {
    static let marker = "spliced.json"
    private static let d = UserDefaults.standard

    static func isProject(_ url: URL) -> Bool {
        FileManager.default.fileExists(atPath: url.appendingPathComponent(marker).path)
    }

    /// The project folder a path is in (itself or a parent), like `spliced` finds it from where you stand.
    static func project(containing url: URL) -> URL? {
        var u = url.standardizedFileURL
        while u.path != "/" {
            if isProject(u) { return u }
            u.deleteLastPathComponent()
        }
        return nil
    }

    static func name(_ url: URL) -> String {
        if let data = try? Data(contentsOf: url.appendingPathComponent(marker)),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let n = obj["name"] as? String, !n.isEmpty { return n }
        return url.lastPathComponent
    }

    // MARK: recents

    static var recents: [URL] {
        (d.stringArray(forKey: "recents") ?? []).map { URL(fileURLWithPath: $0) }
    }

    static func noteOpened(_ url: URL) {
        var r = (d.stringArray(forKey: "recents") ?? []).filter { $0 != url.path }
        r.insert(url.path, at: 0)
        d.set(Array(r.prefix(20)), forKey: "recents")
        NSDocumentController.shared.noteNewRecentDocumentURL(url)
        NotificationCenter.default.post(name: .recentsChanged, object: nil)
    }

    static func forget(_ url: URL) {
        d.set((d.stringArray(forKey: "recents") ?? []).filter { $0 != url.path }, forKey: "recents")
        NotificationCenter.default.post(name: .recentsChanged, object: nil)
    }

    // MARK: session

    static var reopen: Bool {
        get { d.object(forKey: "reopen") as? Bool ?? true }
        set { d.set(newValue, forKey: "reopen") }
    }

    static var openAtQuit: [URL] {
        get { (d.stringArray(forKey: "openAtQuit") ?? []).map { URL(fileURLWithPath: $0) } }
        set { d.set(newValue.map(\.path), forKey: "openAtQuit") }
    }

    // MARK: ports

    /// This project's port: the one it had last time if it is free, otherwise the first free one from 8766 up
    /// (8765 is where `spliced open` serves from a terminal).
    static func port(for url: URL) -> Int {
        var ports = d.dictionary(forKey: "ports") as? [String: Int] ?? [:]
        if let p = ports[url.path], isFree(p) { return p }
        let taken = Set(ports.filter { $0.key != url.path }.values)
        var p = 8766
        while taken.contains(p) || !isFree(p) { p += 1 }
        ports[url.path] = p
        d.set(ports, forKey: "ports")
        return p
    }

    static func isFree(_ port: Int) -> Bool {
        let s = socket(AF_INET, SOCK_STREAM, 0)
        guard s >= 0 else { return false }
        defer { close(s) }
        var one: Int32 = 1   // as the server binds (allow_reuse_address): a port it just let go of is still ours
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, socklen_t(MemoryLayout<Int32>.size))
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(UInt16(port).bigEndian)
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        return withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(s, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0 }
        }
    }
}

extension Notification.Name {
    static let recentsChanged = Notification.Name("SplicedRecentsChanged")
}
