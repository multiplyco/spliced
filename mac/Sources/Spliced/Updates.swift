import AppKit

/// Is there a newer Spliced, and putting it in. Two kinds of copy:
/// - built from a checkout (mac/build/Spliced.app inside a git clone, as for the people who work on Spliced, or a copy
///   of it moved elsewhere, say to Applications: build.sh writes the clone's path into its Info.plist as SplicedCheckout):
///   newer is commits on the branch's upstream; updating pulls them, builds the app again, puts the new build where
///   this copy is, and opens it.
/// - a release (the .app from a .dmg): newer is the latest GitHub release of the repo in Info.plist (SplicedReleases);
///   updating downloads its .dmg, puts the new app where this one is, and opens it.
/// Checked at launch and every few hours; "Check for Updates…" asks now. Says nothing when it can't tell (offline,
/// no such repo yet). Open projects come back after the relaunch (Projects.openAtQuit).
final class Updates {
    static let shared = Updates()

    struct Release {
        let version: String      // "0.2.0", or "3 new changes" for a checkout
        let detail: String       // a line to show under it (the newest change, the release's name)
        let page: URL?           // the release page or the repo, to read about it
        let asset: URL?          // a release's .dmg
    }
    enum State: Equatable { case idle, checking, updating(String), failed(String) }

    private(set) var available: Release? { didSet { changed() } }
    private(set) var state: State = .idle { didSet { changed() } }
    private(set) var lastChecked: Date?
    private var timer: Timer?
    private let log = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Spliced/update.log")

    /// The git clone this app was built in, if it was: the one it sits in (…/mac/build/Spliced.app), or for a copy
    /// moved out of it, the one its Info.plist names (SplicedCheckout), while that clone is still there.
    let checkout: URL? = {
        let fm = FileManager.default
        let isClone = { (u: URL) in fm.fileExists(atPath: u.appendingPathComponent(".git").path) && fm.fileExists(atPath: u.appendingPathComponent("mac/build.sh").path) }
        let app = Bundle.main.bundleURL.standardizedFileURL
        if app.deletingLastPathComponent().lastPathComponent == "build",
           app.deletingLastPathComponent().deletingLastPathComponent().lastPathComponent == "mac" {
            let repo = app.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            if isClone(repo) { return repo }
        }
        if let path = Bundle.main.object(forInfoDictionaryKey: "SplicedCheckout") as? String, !path.isEmpty {
            let repo = URL(fileURLWithPath: path).standardizedFileURL
            if isClone(repo) { return repo }
        }
        return nil
    }()

    var kind: String { checkout != nil ? "checkout" : "release" }

    func start() {
        check()
        timer = Timer.scheduledTimer(withTimeInterval: 4 * 3600, repeats: true) { [weak self] _ in self?.check() }
    }

    /// Check again if the last check is older than half an hour: when the app comes to the front, so changes pushed
    /// while you were elsewhere show up without waiting for the next four-hourly check.
    func checkIfStale() {
        if case .checking = state { return }
        if case .updating = state { return }
        if let c = lastChecked, Date().timeIntervalSince(c) < 30 * 60 { return }
        check()
    }

    private func changed() {
        DispatchQueue.main.async { NotificationCenter.default.post(name: .updateChanged, object: nil) }
    }

    /// What the page shows (SP.native.ask("update")): {kind, state, version?, detail?, checked?}
    var summary: [String: Any] {
        var d: [String: Any] = ["kind": kind, "current": Bundle.main.shortVersion]
        switch state {
        case .idle: d["state"] = available == nil ? "current" : "available"
        case .checking: d["state"] = "checking"
        case .updating(let step): d["state"] = "updating"; d["step"] = step
        case .failed(let why): d["state"] = "failed"; d["error"] = why
        }
        if let a = available { d["version"] = a.version; d["detail"] = a.detail }
        if let c = lastChecked { d["checked"] = Int(c.timeIntervalSince1970) }
        return d
    }

    // MARK: checking

    func check() {
        if case .updating = state { return }
        state = .checking
        if let repo = checkout { checkCheckout(repo) } else { checkRelease() }
    }

    private func finish(_ r: Release?) {
        DispatchQueue.main.async {
            self.lastChecked = Date()
            self.available = r
            if self.state == .checking { self.state = .idle }
        }
    }

    private func checkCheckout(_ repo: URL) {
        DispatchQueue.global(qos: .utility).async {
            let git = { (args: [String]) in Updates.run("/usr/bin/git", ["-C", repo.path] + args) }
            // the branch must follow an upstream; a detached or local-only checkout has nothing to pull
            guard git(["rev-parse", "--abbrev-ref", "@{u}"]).ok else { return self.finish(nil) }
            _ = git(["fetch", "--quiet"])
            let n = Int(git(["rev-list", "--count", "HEAD..@{u}"]).out.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
            guard n > 0 else { return self.finish(nil) }
            let newest = git(["log", "-1", "--format=%s", "@{u}"]).out.trimmingCharacters(in: .whitespacesAndNewlines)
            let remote = git(["remote", "get-url", "origin"]).out.trimmingCharacters(in: .whitespacesAndNewlines)
            let page = Updates.webURL(remote)
            self.finish(Release(version: n == 1 ? "1 new change" : "\(n) new changes", detail: newest, page: page, asset: nil))
        }
    }

    private func checkRelease() {
        let api = ProcessInfo.processInfo.environment["SPLICED_RELEASES_URL"]   // a stand-in server, for checks of this code
            ?? (Bundle.main.object(forInfoDictionaryKey: "SplicedReleases") as? String).map { "https://api.github.com/repos/\($0)/releases/latest" }
        guard let api, let url = URL(string: api) else { return finish(nil) }
        var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        req.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        req.setValue("Spliced/\(Bundle.main.shortVersion)", forHTTPHeaderField: "User-Agent")
        URLSession.shared.dataTask(with: req) { data, resp, _ in
            guard (resp as? HTTPURLResponse)?.statusCode == 200, let data,
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let tag = obj["tag_name"] as? String else { return self.finish(nil) }
            let v = tag.hasPrefix("v") ? String(tag.dropFirst()) : tag
            guard Updates.newer(v, than: Bundle.main.shortVersion) else { return self.finish(nil) }
            let assets = (obj["assets"] as? [[String: Any]]) ?? []
            let dmg = assets.compactMap { ($0["browser_download_url"] as? String).flatMap(URL.init(string:)) }.first { $0.pathExtension == "dmg" }
            let page = (obj["html_url"] as? String).flatMap(URL.init(string:))
            self.finish(Release(version: v, detail: (obj["name"] as? String) ?? "Spliced \(v)", page: page, asset: dmg))
        }.resume()
    }

    // MARK: updating

    /// Put the new version in and open it. Projects that are open come back after the relaunch.
    func install() {
        guard let a = available else { return }
        if case .updating = state { return }
        if let repo = checkout { return installCheckout(repo) }
        guard let dmg = a.asset else {   // a release without a disk image: the page is all there is
            if let p = a.page { NSWorkspace.shared.open(p) }
            return
        }
        installRelease(dmg)
    }

    private func installCheckout(_ repo: URL) {
        state = .updating("Getting the new changes")
        DispatchQueue.global(qos: .userInitiated).async {
            self.note("update \(Date()) in \(repo.path)")
            let pull = Updates.run("/usr/bin/git", ["-C", repo.path, "pull", "--ff-only", "--quiet"], log: self.log)
            guard pull.ok else { return self.fail("git pull didn't go through: " + Updates.last(pull.out)) }
            DispatchQueue.main.async { self.state = .updating("Building the new app") }
            let build = Updates.run(repo.appendingPathComponent("mac/build.sh").path, [], env: Engine.environment, cwd: repo, log: self.log)
            guard build.ok else { return self.fail("The build failed: " + Updates.last(build.out)) }
            let here = Bundle.main.bundleURL.standardizedFileURL
            let built = repo.appendingPathComponent("mac/build/Spliced.app").standardizedFileURL
            if here == built { return DispatchQueue.main.async { self.relaunch(here) } }
            // a copy moved out of the clone (to Applications): the new build goes where this copy is
            DispatchQueue.main.async { self.state = .updating("Putting it in") }
            let staged = here.deletingLastPathComponent().appendingPathComponent(".Spliced-update.app")
            try? FileManager.default.removeItem(at: staged)
            let copy = Updates.run("/usr/bin/ditto", [built.path, staged.path], log: self.log)
            guard copy.ok else { return self.fail("Couldn't write next to \(here.deletingLastPathComponent().path): is it writable?") }
            DispatchQueue.main.async { self.relaunch(here, replacingWith: staged) }
        }
    }

    private func installRelease(_ dmg: URL) {
        state = .updating("Downloading")
        URLSession.shared.downloadTask(with: dmg) { file, resp, err in
            guard let file, (resp as? HTTPURLResponse)?.statusCode ?? 200 < 400 else { return self.fail("The download failed: \(err?.localizedDescription ?? "no file")") }
            DispatchQueue.main.async { self.state = .updating("Putting it in") }
            let fm = FileManager.default
            let work = fm.temporaryDirectory.appendingPathComponent("spliced-update-\(UUID().uuidString)")
            let mount = work.appendingPathComponent("mnt")
            try? fm.createDirectory(at: mount, withIntermediateDirectories: true)
            let image = work.appendingPathComponent("Spliced.dmg")
            do { try fm.moveItem(at: file, to: image) } catch { return self.fail("Couldn't keep the download: \(error.localizedDescription)") }
            let attach = Updates.run("/usr/bin/hdiutil", ["attach", image.path, "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", mount.path], log: self.log)
            guard attach.ok else { return self.fail("Couldn't open the disk image") }
            defer { _ = Updates.run("/usr/bin/hdiutil", ["detach", mount.path, "-quiet"]) }
            guard let app = (try? fm.contentsOfDirectory(at: mount, includingPropertiesForKeys: nil))?.first(where: { $0.pathExtension == "app" }) else {
                return self.fail("The disk image has no app in it")
            }
            // next to this app, so the swap is a rename on the same disk
            let here = Bundle.main.bundleURL
            let staged = here.deletingLastPathComponent().appendingPathComponent(".Spliced-update.app")
            try? fm.removeItem(at: staged)
            let copy = Updates.run("/usr/bin/ditto", [app.path, staged.path], log: self.log)
            guard copy.ok else { return self.fail("Couldn't write next to \(here.deletingLastPathComponent().path): is it writable?") }
            DispatchQueue.main.async { self.relaunch(here, replacingWith: staged) }
        }.resume()
    }

    /// Quit, and once this process has gone (projects' servers stopped, the open ones remembered), open the new app.
    private func relaunch(_ app: URL, replacingWith staged: URL? = nil) {
        state = .updating("Opening the new version")
        let pid = ProcessInfo.processInfo.processIdentifier
        let q = { (u: URL) in "'" + u.path.replacingOccurrences(of: "'", with: "'\\''") + "'" }
        var script = "while kill -0 \(pid) 2>/dev/null; do sleep 0.2; done\n"
        if let staged { script += "rm -rf \(q(app)) && mv \(q(staged)) \(q(app))\n" }
        script += "open -n \(q(app))\n"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-c", script]
        do { try p.run() } catch { return fail("Couldn't start the new version: \(error.localizedDescription)") }
        NSApp.terminate(nil)
    }

    private func fail(_ why: String) {
        note("failed: \(why)")
        DispatchQueue.main.async { self.state = .failed(why + " (the whole story: ~/Library/Logs/Spliced/update.log)") }
    }

    private func note(_ line: String) {
        try? FileManager.default.createDirectory(at: log.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let h = try? FileHandle(forWritingTo: log) { h.seekToEndOfFile(); h.write(Data((line + "\n").utf8)); try? h.close() }
        else { try? Data((line + "\n").utf8).write(to: log) }
    }

    // MARK: helpers

    @discardableResult
    static func run(_ exe: String, _ args: [String], env: [String: String]? = nil, cwd: URL? = nil, log: URL? = nil) -> (ok: Bool, out: String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: exe)
        p.arguments = args
        if let env { p.environment = env }
        if let cwd { p.currentDirectoryURL = cwd }
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do { try p.run() } catch { return (false, error.localizedDescription) }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        let out = String(decoding: data, as: UTF8.self)
        if let log, let h = try? FileHandle(forWritingTo: log) { h.seekToEndOfFile(); h.write(data); try? h.close() }
        return (p.terminationStatus == 0, out)
    }

    static func last(_ out: String) -> String {
        let lines = out.split(separator: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
        return lines.last { !$0.isEmpty } ?? "no output"
    }

    /// git@github.com:org/repo.git or https://github.com/org/repo.git -> https://github.com/org/repo/commits
    static func webURL(_ remote: String) -> URL? {
        var s = remote
        if s.hasPrefix("git@") { s = "https://" + s.dropFirst(4).replacingOccurrences(of: ":", with: "/") }
        if s.hasSuffix(".git") { s = String(s.dropLast(4)) }
        return URL(string: s + "/commits")
    }

    /// "0.10.0" is newer than "0.9.2"; a build that isn't a release ("dev") never asks.
    static func newer(_ a: String, than b: String) -> Bool {
        let p = { (s: String) in s.split(separator: ".").map { Int($0) ?? -1 } }
        let x = p(a), y = p(b)
        guard !y.contains(-1), !x.contains(-1) else { return false }
        for i in 0..<max(x.count, y.count) {
            let l = i < x.count ? x[i] : 0, r = i < y.count ? y[i] : 0
            if l != r { return l > r }
        }
        return false
    }
}

extension Notification.Name {
    static let updateChanged = Notification.Name("SplicedUpdateChanged")
}
