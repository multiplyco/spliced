import Foundation

/// One project's server: `spliced --project <folder> open --no-open --port <n>`, the same server a terminal runs.
/// If the project is already served (a terminal, another copy of the app), the window uses that one and leaves it
/// running when it closes.
final class Server {
    enum State { case starting, ready(URL), failed(String), stopped(String) }

    let project: URL
    private(set) var state: State = .starting { didSet { let s = state; DispatchQueue.main.async { self.onChange?(s) } } }
    var onChange: ((State) -> Void)?
    private var process: Process?
    private(set) var owned = false
    private var log = Data()
    private let lock = NSLock()
    private var stopping = false

    init(project: URL) { self.project = project }

    var logText: String { lock.lock(); defer { lock.unlock() }; return String(decoding: log, as: UTF8.self) }
    var logFile: URL {
        let dir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Spliced")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent(project.lastPathComponent + ".log")
    }

    func start() {
        state = .starting
        stopping = false
        DispatchQueue.global(qos: .userInitiated).async { self.launch() }
    }

    private func launch() {
        if let url = running() { owned = false; state = .ready(url); return }
        guard let cmd = Engine.command else {
            state = .failed("Spliced's engine isn't in this copy of the app, and no spliced command was found on this Mac.")
            return
        }
        let port = Projects.port(for: project)
        let p = Process()
        p.executableURL = cmd
        p.arguments = ["--project", project.path, "open", "--no-open", "--port", String(port)]
        var env = Engine.environment
        env["SPLICED_PARENT_PID"] = String(getpid())   // the server stops if the app goes away without stopping it
        p.environment = env
        p.currentDirectoryURL = project
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        p.standardInput = FileHandle.nullDevice
        lock.lock(); log = Data("$ \(cmd.path) \(p.arguments!.joined(separator: " "))\n".utf8); lock.unlock()
        FileManager.default.createFile(atPath: logFile.path, contents: nil)
        let file = try? FileHandle(forWritingTo: logFile)
        pipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            guard let self, !d.isEmpty else { return }
            self.lock.lock()
            self.log.append(d)
            if self.log.count > 400_000 { self.log = self.log.suffix(200_000) }
            self.lock.unlock()
            file?.write(d)
        }
        p.terminationHandler = { [weak self] proc in
            guard let self else { return }
            pipe.fileHandleForReading.readabilityHandler = nil
            if self.stopping { return }
            if case .ready = self.state {
                self.state = .stopped("Spliced stopped (exit \(proc.terminationStatus)).")
            }
        }
        do { try p.run() } catch {
            state = .failed("Couldn't start \(cmd.path): \(error.localizedDescription)")
            return
        }
        process = p
        owned = true
        // Ready when it answers. The first start on a big library builds its index, so give it time.
        let deadline = Date().addingTimeInterval(300)
        while Date() < deadline {
            if stopping { return }
            if let root = info(port: port), sameFolder(root, project) {
                state = .ready(URL(string: "http://127.0.0.1:\(port)/app/")!)
                return
            }
            if !p.isRunning {
                if let url = running() { owned = false; process = nil; state = .ready(url); return }   // it found one already up
                usleep(150_000)   // let the last lines arrive
                state = .failed(tail())
                return
            }
            usleep(150_000)
        }
        state = .failed("Spliced didn't answer within five minutes.\n\n" + tail())
    }

    func stop() {
        stopping = true
        guard owned, let p = process, p.isRunning else { return }
        p.terminate()   // SIGTERM: the server tidies up (.cache/server.json) and exits
        let deadline = Date().addingTimeInterval(3)
        while p.isRunning && Date() < deadline { usleep(30_000) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
    }

    func restart() {
        stop()
        process = nil
        start()
    }

    private func tail() -> String {
        let lines = logText.split(separator: "\n", omittingEmptySubsequences: false)
        return lines.suffix(30).joined(separator: "\n")
    }

    /// The server already serving this project, as `.cache/server.json` says, if it answers and serves this folder.
    private func running() -> URL? {
        let f = project.appendingPathComponent(".cache/server.json")
        guard let data = try? Data(contentsOf: f),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let port = obj["port"] as? Int,
              let root = info(port: port), sameFolder(root, project) else { return nil }
        return URL(string: "http://127.0.0.1:\(port)/app/")
    }

    /// GET /api/info on a port: the folder that server serves, or nil.
    private func info(port: Int) -> String? {
        guard let url = URL(string: "http://127.0.0.1:\(port)/api/info") else { return nil }
        var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 1.5)
        req.httpMethod = "GET"
        let sem = DispatchSemaphore(value: 0)
        var root: String?
        URLSession.shared.dataTask(with: req) { data, resp, _ in
            if (resp as? HTTPURLResponse)?.statusCode == 200, let data,
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { root = obj["root"] as? String }
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 2)
        return root
    }

    private func sameFolder(_ a: String, _ b: URL) -> Bool {
        URL(fileURLWithPath: a).resolvingSymlinksInPath().path == b.resolvingSymlinksInPath().path
    }
}
