import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuItemValidation {
    private var windows: [ProjectWindowController] = []
    private var start: StartWindowController?
    private var settings: SettingsWindowController?
    private var quitting = false
    private var launchedWithFolders = false
    private let term = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
    private let updateItem = NSMenuItem(title: "", action: #selector(installUpdate), keyEquivalent: "")

    private func showUpdate() {
        let u = Updates.shared
        switch u.state {
        case .updating(let step): updateItem.isHidden = false; updateItem.title = "Updating: \(step)…"
        default:
            updateItem.isHidden = u.available == nil
            updateItem.title = u.available.map { u.checkout != nil ? "Update Spliced (\($0.version))" : "Update to Spliced \($0.version)" } ?? ""
        }
    }

    @objc func installUpdate(_ sender: Any?) { Updates.shared.install() }
    @objc func checkForUpdates(_ sender: Any?) {
        Updates.shared.check()
        // say what it found, once it has
        var token: NSObjectProtocol?
        token = NotificationCenter.default.addObserver(forName: .updateChanged, object: nil, queue: .main) { _ in
            let u = Updates.shared
            guard u.state != .checking else { return }
            if let t = token { NotificationCenter.default.removeObserver(t) }
            let a = NSAlert()
            if let r = u.available {
                a.messageText = u.checkout != nil ? "\(r.version) for Spliced" : "Spliced \(r.version) is out"
                a.informativeText = (u.checkout != nil ? "Newest: \(r.detail)\n\n" : "") + "Spliced closes, updates and opens again with your projects."
                a.addButton(withTitle: "Update app"); a.addButton(withTitle: "Later")
                if a.runModal() == .alertFirstButtonReturn { u.install() }
            } else if case .failed(let why) = u.state {
                a.messageText = "Couldn't check for updates"; a.informativeText = why; a.runModal()
            } else {
                a.messageText = "Spliced is up to date"
                a.informativeText = u.checkout != nil ? "Your checkout has every change on its branch." : "Version \(Bundle.main.shortVersion) is the newest."
                a.runModal()
            }
        }
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        NSApp.mainMenu = makeMenu()
        Debug.install()
        // kill <pid> (a logout, a script) quits like Cmd-Q, so every project's server is stopped
        signal(SIGTERM, SIG_IGN)
        term.setEventHandler { NSApp.terminate(nil) }
        term.resume()
        NotificationCenter.default.addObserver(forName: .updateChanged, object: nil, queue: .main) { [weak self] _ in self?.showUpdate() }
        Updates.shared.start()
        NotificationCenter.default.addObserver(forName: .importsChanged, object: nil, queue: .main) { [weak self] _ in
            let n = self?.windows.reduce(0) { $0 + $1.importsRunning } ?? 0
            NSApp.dockTile.badgeLabel = n > 0 ? String(n) : nil
        }
        Notifier.onOpen = { [weak self] path in self?.open(URL(fileURLWithPath: path)) }
        _ = Engine.environment   // the login shell's PATH, once, before the first project needs it
        if launchedWithFolders { return }
        let again = Projects.reopen ? Projects.openAtQuit.filter(Projects.isProject) : []
        if again.isEmpty { showStart() } else { again.forEach { open($0) } }
    }

    /// A folder dropped on the Dock icon, chosen in Open Recent, or `open -a Spliced <folder>`.
    func application(_ app: NSApplication, open urls: [URL]) {
        launchedWithFolders = true
        for u in urls { openOrOffer(u) }
    }

    func applicationDidBecomeActive(_ n: Notification) { Updates.shared.checkIfStale() }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows: Bool) -> Bool {
        if !hasVisibleWindows { showStart() }
        return true
    }

    func applicationShouldTerminate(_ s: NSApplication) -> NSApplication.TerminateReply {
        quitting = true
        Projects.openAtQuit = windows.map(\.project)
        for w in windows { w.server.stop() }
        return .terminateNow
    }

    // MARK: projects

    /// Open a project in its own window. `replacing` a window switches that window to it: the new one takes its place
    /// and the old one closes (its server stops). A project already open in a window is brought to the front.
    func open(_ project: URL, replacing old: ProjectWindowController? = nil) {
        let p = project.standardizedFileURL
        if old?.project == p { return }
        if let w = windows.first(where: { $0.project == p }) {
            w.showWindow(nil); w.window?.makeKeyAndOrderFront(nil)
            old?.window?.close()
            return
        }
        let w = ProjectWindowController(project: p)
        if let frame = old?.window?.frame { w.window?.setFrame(frame, display: false) }
        w.onClose = { [weak self] c in
            guard let self, !self.quitting else { return }
            self.windows.removeAll { $0 === c }
            if self.windows.isEmpty { self.showStart() }
        }
        windows.append(w)
        w.showWindow(nil)
        Projects.noteOpened(p)
        start?.close()
        old?.window?.close()
    }

    /// A folder: the project it is (or is in), or the offer to make it one.
    func openOrOffer(_ url: URL, replacing old: ProjectWindowController? = nil) {
        if let p = Projects.project(containing: url) { return open(p, replacing: old) }
        let a = NSAlert()
        a.messageText = "“\(url.lastPathComponent)” isn't a Spliced project yet"
        a.informativeText = "Make it one? Spliced adds a spliced.json and a few empty folders for your library, and changes nothing that is already there."
        a.addButton(withTitle: "Make It a Project")
        a.addButton(withTitle: "Cancel")
        if a.runModal() == .alertFirstButtonReturn { initAndOpen(url, replacing: old) }
    }

    private func initAndOpen(_ url: URL, replacing old: ProjectWindowController? = nil) {
        guard let cmd = Engine.command else { return fail("Spliced's engine is missing from this copy of the app.") }
        do {
            let r = try Engine.run(cmd, ["init", url.path])
            if r.status != 0 || !Projects.isProject(url) { return fail(r.output) }
            open(url, replacing: old)
        } catch { fail(error.localizedDescription) }
    }

    private func fail(_ why: String) {
        let a = NSAlert()
        a.messageText = "Spliced couldn't make the project"
        a.informativeText = why.trimmingCharacters(in: .whitespacesAndNewlines)
        a.runModal()
    }

    private var current: ProjectWindowController? {
        windows.first { $0.window == NSApp.keyWindow } ?? windows.first { $0.window == NSApp.mainWindow }
    }

    func showStart() {
        if start == nil {
            start = StartWindowController(open: { [weak self] in self?.openOrOffer($0) },
                                          newProject: { [weak self] in self?.newProject(nil) },
                                          openPanel: { [weak self] in self?.openProject(nil) })
        }
        start?.showWindow(nil)
        start?.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    // MARK: menu actions

    @objc func newProject(_ sender: Any?) { makeProject() }

    private func makeProject(replacing old: ProjectWindowController? = nil) {
        let p = NSSavePanel()
        p.title = "New Project"
        p.message = "A folder for your library, your boards and your films."
        p.nameFieldLabel = "Project:"
        p.nameFieldStringValue = "My films"
        p.prompt = "Create"
        p.canCreateDirectories = true
        guard p.runModal() == .OK, let url = p.url else { return }
        do { try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true) } catch { return fail(error.localizedDescription) }
        initAndOpen(url, replacing: old)
    }

    @objc func openProject(_ sender: Any?) { chooseProject() }

    private func chooseProject(replacing old: ProjectWindowController? = nil) {
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = false
        p.message = "Choose a project folder (one with a spliced.json), or any folder to make it one."
        p.prompt = "Open"
        guard p.runModal() == .OK, let url = p.url else { return }
        openOrOffer(url, replacing: old)
    }

    /// Close a project's window and go back to the start window, to open or make another.
    func closeProject(_ w: ProjectWindowController) {
        w.window?.close()
        showStart()
    }

    /// The menu under the project's name at the top of the page's sidebar: the recent projects (choosing one switches
    /// this window to it), open or make another in its place, or close this one and go back to the start window.
    func projectMenu(for w: ProjectWindowController) -> NSMenu {
        let m = NSMenu(title: "Projects")
        m.autoenablesItems = false
        let head = NSMenuItem(title: "Projects", action: nil, keyEquivalent: "")
        head.isEnabled = false
        m.addItem(head)
        let here = NSMenuItem(title: Projects.name(w.project), action: nil, keyEquivalent: "")
        here.state = .on
        here.toolTip = (w.project.path as NSString).abbreviatingWithTildeInPath
        m.addItem(here)
        for url in Projects.recents.filter({ $0.standardizedFileURL != w.project && Projects.isProject($0) }).prefix(9) {
            let i = ActionItem(Projects.name(url)) { [weak self, weak w] in self?.open(url, replacing: w) }
            i.toolTip = (url.path as NSString).abbreviatingWithTildeInPath
            m.addItem(i)
        }
        m.addItem(.separator())
        m.addItem(ActionItem("Open Another Project…") { [weak self, weak w] in self?.chooseProject(replacing: w) })
        m.addItem(ActionItem("New Project…") { [weak self, weak w] in self?.makeProject(replacing: w) })
        m.addItem(.separator())
        m.addItem(ActionItem("Show in Finder") { [weak w] in w?.revealProject() })
        m.addItem(ActionItem("All Projects…") { [weak self] in self?.showStart() })
        m.addItem(ActionItem("Close Project") { [weak self, weak w] in if let w { self?.closeProject(w) } })
        return m
    }

    @objc func showStartWindow(_ sender: Any?) { showStart() }

    @objc func showSettings(_ sender: Any?) {
        if settings == nil { settings = SettingsWindowController() }
        settings?.showWindow(nil)
        settings?.window?.makeKeyAndOrderFront(nil)
    }

    @objc func installCLI(_ sender: Any?) { CommandLineTool.install() }

    @objc func addReferences(_ sender: Any?) { current?.addReferences() }
    @objc func addFolder(_ sender: Any?) { current?.addFolder() }
    @objc func connectAI(_ sender: Any?) { current?.connectAI() }
    @objc func goRoute(_ sender: NSMenuItem) { if let r = sender.representedObject as? String { current?.go(r) } }
    @objc func reloadPage(_ sender: Any?) { current?.reload() }
    @objc func goBack(_ sender: Any?) { current?.back() }
    @objc func goForward(_ sender: Any?) { current?.forward() }
    @objc func showRecent(_ sender: Any?) { current?.recent() }
    @objc func zoomIn(_ sender: Any?) { current?.zoom(0.1) }
    @objc func zoomOut(_ sender: Any?) { current?.zoom(-0.1) }
    @objc func actualSize(_ sender: Any?) { current?.zoom(nil) }
    @objc func revealProject(_ sender: Any?) { current?.revealProject() }
    @objc func openInTerminal(_ sender: Any?) { current?.openInTerminal() }
    @objc func showLog(_ sender: Any?) { current?.showLog() }
    @objc func closeCurrentProject(_ sender: Any?) { if let w = current { closeProject(w) } }
    @objc func restartServer(_ sender: Any?) { current?.restartServer() }
    @objc func openHelp(_ sender: Any?) { NSWorkspace.shared.open(URL(string: "https://github.com/multiplyco/spliced#readme")!) }

    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        let needsProject: Set<Selector> = [#selector(addReferences), #selector(addFolder), #selector(connectAI), #selector(goRoute),
                                           #selector(reloadPage), #selector(goBack), #selector(goForward), #selector(showRecent), #selector(zoomIn), #selector(zoomOut), #selector(actualSize),
                                           #selector(revealProject), #selector(openInTerminal), #selector(showLog), #selector(restartServer),
                                           #selector(closeCurrentProject)]
        if item.action == #selector(installUpdate) { if case .updating = Updates.shared.state { return false }; return Updates.shared.available != nil }
        if item.action == #selector(checkForUpdates) { if case .updating = Updates.shared.state { return false }; return true }
        if item.action == #selector(goBack) { return current?.canGoBack ?? false }
        if item.action == #selector(goForward) { return current?.canGoForward ?? false }
        if let a = item.action, needsProject.contains(a) { return current != nil }
        if item.action == #selector(installCLI) { return CommandLineTool.status.canInstall }
        return true
    }

    // MARK: the menu bar

    private func makeMenu() -> NSMenu {
        let bar = NSMenu()
        @discardableResult func menu(_ title: String, _ items: [NSMenuItem]) -> NSMenu {
            let m = NSMenu(title: title)
            items.forEach(m.addItem)
            let top = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            top.submenu = m
            bar.addItem(top)
            return m
        }
        func item(_ title: String, _ action: Selector?, _ key: String = "", _ mods: NSEvent.ModifierFlags = .command, route: String? = nil) -> NSMenuItem {
            let i = NSMenuItem(title: title, action: action, keyEquivalent: key)
            i.keyEquivalentModifierMask = mods
            i.representedObject = route
            return i
        }
        let sep = { NSMenuItem.separator() }

        updateItem.isHidden = true
        menu("Spliced", [
            item("About Spliced", #selector(NSApplication.orderFrontStandardAboutPanel(_:)), ""),
            updateItem,
            item("Check for Updates…", #selector(checkForUpdates)),
            sep(),
            item("Settings…", #selector(showSettings), ","),
            item("Install Command Line Tool…", #selector(installCLI)),
            sep(),
            item("Hide Spliced", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:))),
            sep(),
            item("Quit Spliced", #selector(NSApplication.terminate(_:)), "q"),
        ])

        let recent = NSMenu(title: "Open Recent")
        recent.addItem(item("Clear Menu", #selector(NSDocumentController.clearRecentDocuments(_:)), ""))
        let recentItem = NSMenuItem(title: "Open Recent", action: nil, keyEquivalent: "")
        recentItem.submenu = recent
        recent.perform(NSSelectorFromString("_setMenuName:"), with: "NSRecentDocumentsMenu")   // AppKit fills it with recent folders
        menu("File", [
            item("New Project…", #selector(newProject), "n", [.command, .shift]),
            item("Open Project…", #selector(openProject), "o"),
            recentItem,
            item("Projects", #selector(showStartWindow), "0", [.command, .shift]),
            sep(),
            item("Add References…", #selector(addReferences), "i", [.command, .shift]),
            item("Add a Folder…", #selector(addFolder), "i", [.command, .option]),
            sep(),
            item("Show Project in Finder", #selector(revealProject), "r", [.command, .shift]),
            item("Open Project in Terminal", #selector(openInTerminal)),
            sep(),
            item("Close Project", #selector(closeCurrentProject), "w", [.command, .shift]),
            item("Close Window", #selector(NSWindow.performClose(_:)), "w"),
        ])

        menu("Edit", [
            item("Undo", Selector(("undo:")), "z"),
            item("Redo", Selector(("redo:")), "z", [.command, .shift]),
            sep(),
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
        ])

        menu("View", [
            item("Back", #selector(goBack), "["),
            item("Forward", #selector(goForward), "]"),
            item("Recently Viewed…", #selector(showRecent), "y"),
            sep(),
            item("Library", #selector(goRoute), "1", route: "#/scenes"),
            item("Boards", #selector(goRoute), "2", route: "#/boards"),
            item("Build", #selector(goRoute), "3", route: "#/build"),
            item("Assets", #selector(goRoute), "4", route: "#/assets"),
            sep(),
            item("Reload", #selector(reloadPage), "r"),
            item("Actual Size", #selector(actualSize), "0"),
            item("Zoom In", #selector(zoomIn), "+"),
            item("Zoom Out", #selector(zoomOut), "-"),
            sep(),
            item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])

        menu("Project", [
            item("Setup", #selector(goRoute), route: "#/setup"),
            item("Connect Your AI…", #selector(connectAI)),
            sep(),
            item("Show Server Log", #selector(showLog)),
            item("Restart Server", #selector(restartServer)),
        ])

        let win = menu("Window", [
            item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
            item("Zoom", #selector(NSWindow.performZoom(_:))),
            sep(),
            item("Bring All to Front", #selector(NSApplication.arrangeInFront(_:))),
        ])
        NSApp.windowsMenu = win

        let help = menu("Help", [item("Spliced Help", #selector(openHelp))])
        NSApp.helpMenu = help
        return bar
    }
}

/// A menu item that runs a closure.
final class ActionItem: NSMenuItem {
    private let run: () -> Void
    init(_ title: String, _ run: @escaping () -> Void) {
        self.run = run
        super.init(title: title, action: #selector(fire), keyEquivalent: "")
        target = self
    }
    required init(coder: NSCoder) { fatalError() }
    @objc private func fire() { run() }
}
