import Foundation

/// The `spliced` command the app runs projects with: the one inside the app (Resources/bin/spliced, the engine copied
/// in at build time), or the one already on this Mac (a checkout installed with `uv tool install -e`, for people who
/// work on Spliced itself). Settings chooses; the built-in one is the default.
enum Engine {
    enum Choice: String, CaseIterable, Identifiable {
        case builtIn = "builtin", system = "system"
        var id: String { rawValue }
        var label: String { self == .builtIn ? "Built into this app" : "The spliced command on this Mac" }
    }

    static var choice: Choice {
        get { Choice(rawValue: UserDefaults.standard.string(forKey: "engine") ?? "") ?? .builtIn }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "engine") }
    }

    static var bundled: URL? {
        guard let u = Bundle.main.resourceURL?.appendingPathComponent("bin/spliced"),
              FileManager.default.isExecutableFile(atPath: u.path) else { return nil }
        return u
    }

    /// The first `spliced` on the person's PATH that isn't this app's own (or a link to it).
    static var system: URL? {
        let own = bundled?.resolvingSymlinksInPath().path
        for dir in (environment["PATH"] ?? "").split(separator: ":") {
            let u = URL(fileURLWithPath: String(dir)).appendingPathComponent("spliced")
            if FileManager.default.isExecutableFile(atPath: u.path), u.resolvingSymlinksInPath().path != own { return u }
        }
        return nil
    }

    /// What runs a project now. Falls back to the other one when the chosen one is missing.
    static var command: URL? { choice == .system ? (system ?? bundled) : (bundled ?? system) }

    /// The environment every engine process gets. An app opened from the Finder or the Dock inherits a bare PATH
    /// (/usr/bin:/bin:...), without Homebrew, uv, node, ffmpeg or claude, so take the PATH the person's login shell
    /// sets, and add the usual places in case that fails.
    static let environment: [String: String] = {
        var env = ProcessInfo.processInfo.environment
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        var dirs = loginPath().split(separator: ":").map(String.init)
        for d in ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin", "\(home)/.cargo/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        where !dirs.contains(d) { dirs.append(d) }
        // the bundled uv (not bin/: a spliced on the PATH would read as installed, and agents would be told a bare `spliced`)
        if let tools = Bundle.main.resourceURL?.appendingPathComponent("tools").path, !dirs.contains(tools) { dirs.append(tools) }
        env["PATH"] = dirs.joined(separator: ":")
        env["PYTHONUNBUFFERED"] = "1"
        env.removeValue(forKey: "SPLICED_PROJECT")
        if let b = bundled { env["SPLICED_COMMAND"] = b.path }
        return env
    }()

    private static func loginPath() -> String {
        let shell = ProcessInfo.processInfo.environment["SHELL"] ?? "/bin/zsh"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: shell)
        p.arguments = ["-l", "-c", "printf '__SPLICED_PATH__%s' \"$PATH\""]
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice
        p.standardInput = FileHandle.nullDevice
        do { try p.run() } catch { return "" }
        let deadline = Date().addingTimeInterval(4)   // a slow or interactive shell profile must not hold the app up
        while p.isRunning && Date() < deadline { usleep(20_000) }
        if p.isRunning { p.terminate(); return "" }
        let s = String(decoding: out.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
        guard let r = s.range(of: "__SPLICED_PATH__") else { return "" }
        return String(s[r.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// The engine's version line (`spliced --version`), for Settings and About.
    static func version(of cmd: URL?) -> String {
        guard let cmd else { return "not found" }
        return (try? run(cmd, ["--version"]).output.trimmingCharacters(in: .whitespacesAndNewlines)) ?? "?"
    }

    struct Result { let status: Int32; let output: String }

    /// Run a short engine command to its end (init, agents install, --version). Not for the server.
    @discardableResult
    static func run(_ cmd: URL, _ args: [String], in dir: URL? = nil) throws -> Result {
        let p = Process()
        p.executableURL = cmd
        p.arguments = args
        p.environment = environment
        if let dir { p.currentDirectoryURL = dir }
        let out = Pipe()
        p.standardOutput = out
        p.standardError = out
        p.standardInput = FileHandle.nullDevice
        try p.run()
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        return Result(status: p.terminationStatus, output: String(decoding: data, as: UTF8.self))
    }
}
