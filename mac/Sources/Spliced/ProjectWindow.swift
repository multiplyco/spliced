import AppKit
import SwiftUI
import WebKit

/// A window on one project: its server, and the app in a web view. Everything the page does is the same page a
/// browser shows; the window adds what a browser can't: a real folder picker, folders dropped on the window,
/// downloads, Finder.
final class ProjectWindowController: NSWindowController, NSWindowDelegate {
    let project: URL
    let server: Server
    private var web: SplicedWebView!
    private var overlay: NSHostingView<StatusView>!
    private let status = StatusModel()
    private var origin: URL?
    private let drag = DragStrip()
    private var nav = (back: false, forward: false)   // what the page last said about the tab you're in
    private var updateWatch: NSObjectProtocol?
    var importsRunning = 0
    var onClose: ((ProjectWindowController) -> Void)?

    init(project: URL) {
        self.project = project
        self.server = Server(project: project)
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 900),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                           backing: .buffered, defer: false)
        win.minSize = NSSize(width: 900, height: 600)
        win.title = Projects.name(project)   // for the Window menu and Mission Control; not drawn
        // No title bar of its own: the page runs to the top edge and its tab strip is the window's top row (with
        // back, forward and recently viewed at its start), like Notion. The traffic lights sit over the sidebar's
        // top strip, which the page leaves empty in the app (html.in-app).
        win.titleVisibility = .hidden
        win.titlebarAppearsTransparent = true
        win.tabbingMode = .disallowed
        // an empty toolbar in the compact style makes the title bar as tall as the page's top row, so the traffic
        // lights sit centred on it
        let bar = NSToolbar(identifier: "spliced.window")
        bar.showsBaselineSeparator = false
        bar.allowsUserCustomization = false
        win.toolbar = bar
        win.toolbarStyle = .unifiedCompact
        win.backgroundColor = NSColor(red: 0.043, green: 0.043, blue: 0.047, alpha: 1)   // the app's dark ground: no white flash
        super.init(window: win)
        win.delegate = self
        win.setFrameAutosaveName("project:" + project.path)
        if !win.setFrameUsingName("project:" + project.path) { win.center() }
        build()
        server.onChange = { [weak self] in self?.serverChanged($0) }
        server.start()
    }

    required init?(coder: NSCoder) { fatalError() }

    private func build() {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .default()
        cfg.mediaTypesRequiringUserActionForPlayback = []   // the welcome film starts by itself, without sound
        cfg.preferences.isElementFullscreenEnabled = true
        cfg.preferences.setValue(true, forKey: "developerExtrasEnabled")
        cfg.userContentController.add(WeakHandler(self), name: "spliced")
        cfg.applicationNameForUserAgent = "Spliced/\(Bundle.main.shortVersion)"
        cfg.userContentController.addUserScript(WKUserScript(source: "document.documentElement.classList.add('in-app')",
                                                             injectionTime: .atDocumentStart, forMainFrameOnly: true))
        web = SplicedWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsMagnification = true
        web.allowsBackForwardNavigationGestures = true
        if #available(macOS 13.3, *) { web.isInspectable = true }
        web.setValue(false, forKey: "drawsBackground")
        web.onFolders = { [weak self] urls in self?.folderDropped(urls) }
        // a newer Spliced, or one being put in: the page shows an Update app button (SPUpdate in app.js)
        updateWatch = NotificationCenter.default.addObserver(forName: .updateChanged, object: nil, queue: .main) { [weak self] _ in
            guard let data = try? JSONSerialization.data(withJSONObject: Updates.shared.summary) else { return }
            self?.js("window.SPUpdate && SPUpdate.changed(\(String(decoding: data, as: UTF8.self)))")
        }
        // Back and forward are each tab's own, kept by the page (SPNav): it reports what is possible ("navState") and
        // the View menu asks it to step. A two-finger swipe still moves through the web view's history; the page
        // recognises those moves and fits them into the tab's.

        status.retry = { [weak self] in self?.server.restart() }
        status.showLog = { [weak self] in self?.showLog() }
        overlay = NSHostingView(rootView: StatusView(model: status, name: Projects.name(project)))

        let root = NSView()
        for v in [web!, drag, overlay!] as [NSView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            root.addSubview(v)
        }
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: root.leadingAnchor), web.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            web.topAnchor.constraint(equalTo: root.topAnchor), web.bottomAnchor.constraint(equalTo: root.bottomAnchor),
            drag.leadingAnchor.constraint(equalTo: web.leadingAnchor), drag.trailingAnchor.constraint(equalTo: web.trailingAnchor),
            drag.topAnchor.constraint(equalTo: web.topAnchor), drag.bottomAnchor.constraint(equalTo: web.bottomAnchor),
            overlay.leadingAnchor.constraint(equalTo: root.leadingAnchor), overlay.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            overlay.topAnchor.constraint(equalTo: root.topAnchor), overlay.bottomAnchor.constraint(equalTo: root.bottomAnchor),
        ])
        window?.contentView = root
    }

    private func serverChanged(_ s: Server.State) {
        switch s {
        case .starting:
            status.phase = .starting
            overlay.isHidden = false
        case .ready(let url):
            origin = url
            if web.url == nil || web.url?.port != url.port { web.load(URLRequest(url: url)) }
            status.phase = .starting   // the overlay goes when the page has drawn (didFinish)
        case .failed(let why):
            status.phase = .failed(why)
            overlay.isHidden = false
        case .stopped(let why):
            status.phase = .failed(why + "\n\n" + server.logText.split(separator: "\n").suffix(20).joined(separator: "\n"))
            overlay.isHidden = false
        }
    }

    // MARK: things the menus ask for

    func js(_ code: String) { web.evaluateJavaScript(code, completionHandler: nil) }
    func go(_ route: String) { js("location.hash = \(jsString(route))") }
    func addReferences() { js("window.Imports && Imports.open()") }
    func addFolder() {
        pickFolder(prompt: "Look inside") { [weak self] url in
            if let url { self?.js("window.Imports && Imports.folder(\(jsString(url.path)))") }
        }
    }
    func reload() { web.reload() }
    var canGoBack: Bool { nav.back }
    var canGoForward: Bool { nav.forward }
    func back() { js("window.SPNav && SPNav.back()") }
    func forward() { js("window.SPNav && SPNav.forward()") }
    func recent() { js("window.SPNav && SPNav.recent()") }
    func zoom(_ by: CGFloat?) { web.pageZoom = by.map { max(0.5, min(2.5, web.pageZoom + $0)) } ?? 1 }
    func restartServer() { server.restart() }
    func revealProject() { NSWorkspace.shared.activateFileViewerSelecting([project]) }

    func showLog() {
        NSWorkspace.shared.open(server.logFile)
    }

    func openInTerminal() {
        let term = URL(fileURLWithPath: "/System/Applications/Utilities/Terminal.app")
        NSWorkspace.shared.open([project], withApplicationAt: term, configuration: NSWorkspace.OpenConfiguration())
    }

    /// Connect your AI: `spliced agents install` for agents that open this folder, and `spliced connect <app>` for the
    /// chat apps found on this Mac (ticked when already connected; unticking one takes this project out of it).
    func connectAI() {
        guard let w = window, let cmd = Engine.command else { return }
        let project = self.project
        DispatchQueue.global(qos: .userInitiated).async {
            struct App: Decodable { let id: String; let name: String; let present: Bool; let connected: Bool }
            struct Status: Decodable { let apps: [App] }
            let out = (try? Engine.run(cmd, ["--project", project.path, "connect", "--json"], in: project))?.output ?? ""
            let apps = (try? JSONDecoder().decode(Status.self, from: Data(out.utf8)))?.apps.filter(\.present) ?? []
            DispatchQueue.main.async { self.showConnect(apps.map { ($0.id, $0.name, $0.connected) }, cmd: cmd, in: w) }
        }
    }

    private func showConnect(_ apps: [(id: String, name: String, connected: Bool)], cmd: URL, in w: NSWindow) {
        let a = NSAlert()
        a.messageText = "Connect your AI to \(Projects.name(project))"
        a.informativeText = "Your AI does the reading and the building; Spliced gives it the tools. Nothing is sent anywhere: this only writes settings on this Mac."
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        func box(_ title: String, _ detail: String, on: Bool, enabled: Bool = true) -> NSButton {
            let b = NSButton(checkboxWithTitle: title, target: nil, action: nil)
            b.state = on ? .on : .off
            b.isEnabled = enabled
            let d = NSTextField(wrappingLabelWithString: detail)
            d.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
            d.textColor = .secondaryLabelColor
            d.preferredMaxLayoutWidth = 340
            let row = NSStackView(views: [b, d])
            row.orientation = .vertical
            row.alignment = .leading
            row.spacing = 2
            stack.addArrangedSubview(row)
            return b
        }
        let folder = box("Agents that open this folder", "Claude Code, Codex, Cursor, Gemini CLI: Spliced's skills, a section in AGENTS.md and its tools in .mcp.json.", on: true)
        var boxes: [(String, Bool, NSButton)] = []
        for app in apps {
            let detail = app.connected ? "Connected. Untick to take this project out."
                : app.id == "claude-desktop" ? "Adds this project to its tools. Quit the Claude app and open it again afterwards."
                : "Adds this project to its tools, from its next chat."
            boxes.append((app.id, app.connected, box(app.name, detail, on: app.connected)))
        }
        if apps.isEmpty {
            let none = NSTextField(wrappingLabelWithString: "No chat app with tools (the Claude desktop app, Cursor, Codex) was found on this Mac.")
            none.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
            none.textColor = .secondaryLabelColor
            stack.addArrangedSubview(none)
        }
        stack.frame = NSRect(x: 0, y: 0, width: 360, height: stack.fittingSize.height)
        a.accessoryView = stack
        a.addButton(withTitle: "Connect")
        a.addButton(withTitle: "Cancel")
        a.beginSheetModal(for: w) { [weak self] r in
            guard r == .alertFirstButtonReturn, let self else { return }
            let project = self.project
            var steps: [[String]] = []
            if folder.state == .on { steps.append(["agents", "install"]) }
            for (id, was, b) in boxes where (b.state == .on) != was { steps.append(b.state == .on ? ["connect", id] : ["connect", id, "--remove"]) }
            guard !steps.isEmpty else { return }
            DispatchQueue.global(qos: .userInitiated).async {
                var ok = true, lines: [String] = []
                for s in steps {
                    let res = try? Engine.run(cmd, ["--project", project.path] + s, in: project)
                    ok = ok && res?.status == 0
                    let text = (res?.output ?? "The engine didn't run.").trimmingCharacters(in: .whitespacesAndNewlines)
                    lines.append(s[0] == "agents" ? (res?.status == 0 ? "Agents that open this folder: ready." : text) : text)
                }
                DispatchQueue.main.async {
                    let done = NSAlert()
                    done.messageText = ok ? "Connected" : "Something didn't connect"
                    done.informativeText = lines.joined(separator: "\n\n")
                    done.beginSheetModal(for: w)
                    self.js("location.hash.startsWith('#/setup') && document.querySelector('[data-a=again]')?.click()")
                }
            }
        }
    }

    // MARK: folders

    private func folderDropped(_ urls: [URL]) {
        guard let first = urls.first else { return }
        js("window.Imports && Imports.folder(\(jsString(first.path)))")
    }

    fileprivate func pickFolder(prompt: String, _ done: @escaping (URL?) -> Void) {
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = false
        p.allowsMultipleSelection = false
        p.prompt = prompt
        p.message = "Choose a folder of pictures, clips and films to bring into the library."
        guard let w = window else { return done(nil) }
        p.beginSheetModal(for: w) { r in done(r == .OK ? p.url : nil) }
    }

    // MARK: NSWindowDelegate

    func windowWillClose(_ notification: Notification) {
        importsRunning = 0
        NotificationCenter.default.post(name: .importsChanged, object: nil)
        web.configuration.userContentController.removeScriptMessageHandler(forName: "spliced")
        server.stop()
        onClose?(self)
    }
}

// MARK: - the page

extension ProjectWindowController: WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, WKScriptMessageHandler {
    private func isOurs(_ url: URL?) -> Bool {
        guard let url, let origin else { return false }
        return ["127.0.0.1", "localhost"].contains(url.host ?? "") && url.port == origin.port
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { return decisionHandler(.cancel) }
        if action.shouldPerformDownload { return decisionHandler(.download) }
        if isOurs(url) || url.scheme == "about" || url.scheme == "blob" || url.scheme == "data" { return decisionHandler(.allow) }
        if action.targetFrame?.isMainFrame == false { return decisionHandler(.allow) }   // an embedded frame (a video player)
        NSWorkspace.shared.open(url)   // everything else (a reference's page, docs) opens in the person's browser
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(response.canShowMIMEType ? .allow : .download)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        status.phase = .ready
        NSAnimationContext.runAnimationGroup({ $0.duration = 0.18; overlay.animator().alphaValue = 0 }) {
            self.overlay.isHidden = true
            self.overlay.alphaValue = 1
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { if let o = self.origin, webView.url == nil { webView.load(URLRequest(url: o)) } }
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

    // target=_blank and window.open: ours in this window, anything else in the browser
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url {
            if isOurs(url) { webView.load(action.request) } else { NSWorkspace.shared.open(url) }
        }
        return nil
    }

    // <input type="file">: the app's "Choose files…"
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let p = NSOpenPanel()
        p.canChooseFiles = true
        p.canChooseDirectories = parameters.allowsDirectories
        p.allowsMultipleSelection = parameters.allowsMultipleSelection
        guard let w = window else { return completionHandler(nil) }
        p.beginSheetModal(for: w) { r in completionHandler(r == .OK ? p.urls : nil) }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = message
        guard let w = window else { return completionHandler() }
        a.beginSheetModal(for: w) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = message
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancel")
        guard let w = window else { return completionHandler(false) }
        a.beginSheetModal(for: w) { completionHandler($0 == .alertFirstButtonReturn) }
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = prompt
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
        field.stringValue = defaultText ?? ""
        a.accessoryView = field
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancel")
        guard let w = window else { return completionHandler(nil) }
        a.window.initialFirstResponder = field
        a.beginSheetModal(for: w) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }

    // downloads (a render, an export): into Downloads, then shown in Finder
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let dir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
        var dest = dir.appendingPathComponent(suggestedFilename)
        let stem = dest.deletingPathExtension().lastPathComponent, ext = dest.pathExtension
        var n = 2
        while FileManager.default.fileExists(atPath: dest.path) {
            dest = dir.appendingPathComponent("\(stem) \(n)" + (ext.isEmpty ? "" : ".\(ext)")); n += 1
        }
        downloads[ObjectIdentifier(download)] = dest
        completionHandler(dest)
    }

    func downloadDidFinish(_ download: WKDownload) {
        if let dest = downloads.removeValue(forKey: ObjectIdentifier(download)) { NSWorkspace.shared.activateFileViewerSelecting([dest]) }
    }

    // SP.native.ask(type, body) from the page
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
        let id = body["id"] as? Int ?? 0
        let answer: (Any?) -> Void = { [weak self] v in
            let json = (try? JSONSerialization.data(withJSONObject: [v ?? NSNull()], options: [.fragmentsAllowed]))
                .map { String(decoding: $0, as: UTF8.self) } ?? "[null]"
            self?.js("SP.native.answer(\(id), \(json)[0])")
        }
        switch type {
        case "pickFolder":
            pickFolder(prompt: "Look inside") { answer($0?.path) }
        case "badge":   // imports running in this project: the Dock icon shows the sum over every window
            importsRunning = body["count"] as? Int ?? 0
            NotificationCenter.default.post(name: .importsChanged, object: nil)
            answer(true)
        case "notify":
            Notifier.post(title: body["title"] as? String ?? "Spliced", body: body["body"] as? String ?? "", project: project,
                          unlessLooking: window)
            answer(true)
        case "dragRegions":   // where the page's top row is empty, so dragging there moves the window
            let rects = { (k: String) in ((body[k] as? [[Double]]) ?? []).map { NSRect(x: $0[0], y: $0[1], width: $0[2], height: $0[3]) } }
            drag.zoom = web.pageZoom
            drag.regions = rects("drag")
            drag.holes = rects("holes")
            answer(true)
        case "update":   // the page's Update app button: {action: status | check | install | page}
            switch body["action"] as? String {
            case "check": Updates.shared.check()
            case "install": Updates.shared.install()
            case "page": if let p = Updates.shared.available?.page { NSWorkspace.shared.open(p) }
            default: break
            }
            answer(Updates.shared.summary)
        case "navState":   // the tab you're in: can it go back or forward (for the View menu)
            nav = (back: body["back"] as? Bool ?? false, forward: body["fwd"] as? Bool ?? false)
            answer(true)
        case "connect":
            connectAI()
            answer(true)
        case "projects":   // the project's name in the sidebar: the menu of projects, above it (or at the pointer)
            guard let app = NSApp.delegate as? AppDelegate else { return answer(false) }
            let menu = app.projectMenu(for: self)
            // "above": the top of the name; the menu ends there, opening upward (the name sits at the window's bottom).
            // "at": where it starts, opening downward, when there is no room above.
            let z = web.pageZoom
            var at = (body["at"] as? [Double]).flatMap { $0.count == 2 ? NSPoint(x: $0[0] * z, y: $0[1] * z) : nil }
            if let a = at, let top = body["above"] as? Double, top * z - menu.size.height > 8 { at = NSPoint(x: a.x, y: top * z - menu.size.height) }
            DispatchQueue.main.async { [weak self] in
                guard let self else { return answer(false) }
                let pointer = self.drag.convert(self.window?.mouseLocationOutsideOfEventStream ?? .zero, from: nil)
                menu.popUp(positioning: nil, at: at ?? pointer, in: self.drag)
                answer(true)
            }
        case "reveal":
            if let rel = body["path"] as? String {
                let u = project.appendingPathComponent(rel).standardizedFileURL
                if u.path.hasPrefix(project.standardizedFileURL.path) { NSWorkspace.shared.activateFileViewerSelecting([u]) }
            }
            answer(true)
        default:
            answer(nil)
        }
    }
}

private var downloads: [ObjectIdentifier: URL] = [:]

/// The page holds its message handler strongly; this keeps that from holding the window.
private final class WeakHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ t: WKScriptMessageHandler) { target = t }
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { target?.userContentController(c, didReceive: m) }
}

func jsString(_ s: String) -> String {
    let data = (try? JSONSerialization.data(withJSONObject: [s])) ?? Data("[\"\"]".utf8)
    return String(String(decoding: data, as: UTF8.self).dropFirst().dropLast())
}

/// The web view, taking folders dropped on it (files still go to the page, which uploads them).
final class SplicedWebView: WKWebView {
    var onFolders: (([URL]) -> Void)?

    private func folders(_ info: NSDraggingInfo) -> [URL] {
        let urls = info.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
        return urls.filter { (try? $0.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true }
    }

    override func draggingEntered(_ info: NSDraggingInfo) -> NSDragOperation { folders(info).isEmpty ? super.draggingEntered(info) : .copy }
    override func draggingUpdated(_ info: NSDraggingInfo) -> NSDragOperation { folders(info).isEmpty ? super.draggingUpdated(info) : .copy }
    override func prepareForDragOperation(_ info: NSDraggingInfo) -> Bool { folders(info).isEmpty ? super.prepareForDragOperation(info) : true }
    override func performDragOperation(_ info: NSDraggingInfo) -> Bool {
        let f = folders(info)
        if f.isEmpty { return super.performDragOperation(info) }
        onFolders?(f)
        return true
    }
}

// MARK: - starting, and when something is wrong

final class StatusModel: ObservableObject {
    enum Phase: Equatable { case starting, ready, failed(String) }
    @Published var phase: Phase = .starting
    var retry: () -> Void = {}
    var showLog: () -> Void = {}
}

struct StatusView: View {
    @ObservedObject var model: StatusModel
    let name: String

    var body: some View {
        ZStack {
            Color(red: 0.043, green: 0.043, blue: 0.047)
            switch model.phase {
            case .starting, .ready:
                VStack(spacing: 18) {
                    Logo().frame(width: 56, height: 56)
                    ProgressView().controlSize(.small).colorScheme(.dark)
                    Text("Opening \(name)").font(.system(size: 13)).foregroundColor(.white.opacity(0.6))
                }
            case .failed(let why):
                VStack(alignment: .leading, spacing: 14) {
                    Text("Spliced couldn't open \(name)").font(.system(size: 17, weight: .semibold)).foregroundColor(.white)
                    ScrollView {
                        Text(why).font(.system(size: 11, design: .monospaced)).foregroundColor(.white.opacity(0.75))
                            .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
                    }
                    .frame(maxHeight: 280)
                    .padding(10)
                    .background(Color.white.opacity(0.05))
                    .cornerRadius(6)
                    HStack {
                        Button("Try again", action: model.retry).keyboardShortcut(.defaultAction)
                        Button("Show the log", action: model.showLog)
                    }
                }
                .frame(maxWidth: 620)
                .padding(40)
            }
        }
    }
}

/// The app icon's mark, drawn from the bundle's icon.
struct Logo: View {
    var body: some View {
        Image(nsImage: NSApp.applicationIconImage).resizable().aspectRatio(contentMode: .fit)
    }
}

extension Bundle {
    var shortVersion: String { infoDictionary?["CFBundleShortVersionString"] as? String ?? "dev" }
}

extension Notification.Name {
    static let importsChanged = Notification.Name("SplicedImportsChanged")
}

/// A transparent view over the page that catches mouse-downs only where the page's top row is empty (the regions
/// the page reports, minus its tabs and buttons), and moves or zooms the window from there. Everywhere else it is
/// invisible to the mouse, so the page gets every click as before.
final class DragStrip: NSView {
    var regions: [NSRect] = []
    var holes: [NSRect] = []
    var zoom: CGFloat = 1
    override var isFlipped: Bool { true }

    private func inside(_ p: NSPoint) -> Bool {
        let q = NSPoint(x: p.x / zoom, y: p.y / zoom)   // the page reports CSS pixels
        return regions.contains { $0.contains(q) } && !holes.contains { $0.contains(q) }
    }

    override func hitTest(_ point: NSPoint) -> NSView? {
        guard let sup = superview else { return nil }
        return inside(convert(point, from: sup)) ? self : nil
    }

    override func mouseDown(with event: NSEvent) {
        if event.clickCount == 2 {
            let action = UserDefaults.standard.string(forKey: "AppleActionOnDoubleClick") ?? "Maximize"
            action == "Minimize" ? window?.performMiniaturize(nil) : window?.performZoom(nil)
        } else {
            window?.performDrag(with: event)
        }
    }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}
