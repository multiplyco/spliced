import AppKit
import SwiftUI

/// The app's own settings (the page has its own, under Settings in the sidebar): which engine runs projects, whether
/// projects reopen at launch, and the command line tool.
final class SettingsWindowController: NSWindowController {
    convenience init() {
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 520, height: 320), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        win.title = "Spliced Settings"
        win.contentView = NSHostingView(rootView: SettingsView())
        win.center()
        self.init(window: win)
    }
}

struct SettingsView: View {
    @State private var engine = Engine.choice
    @State private var reopen = Projects.reopen
    @State private var builtIn = "…"
    @State private var system = "…"
    @State private var cli = CommandLineTool.status

    var body: some View {
        Form {
            Section {
                Picker("Run projects with", selection: $engine) {
                    ForEach(Engine.Choice.allCases) { Text($0.label).tag($0) }
                }
                .pickerStyle(.radioGroup)
                .onChange(of: engine) { Engine.choice = $0 }
                LabeledContent("Built in", value: builtIn)
                LabeledContent("On this Mac", value: system)
                Text("The spliced command on this Mac is for people working on Spliced itself, from a checkout. A change applies to projects opened after it.")
                    .font(.caption).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Section {
                Toggle("Reopen the projects that were open when Spliced quit", isOn: $reopen).onChange(of: reopen) { Projects.reopen = $0 }
            }
            Section {
                LabeledContent("Command line tool") {
                    HStack {
                        Text(cli.label).foregroundColor(.secondary)
                        if cli.canInstall { Button("Install") { CommandLineTool.install(); cli = CommandLineTool.status } }
                    }
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 520)
        .task {
            let b = Engine.bundled, s = Engine.system
            let (bv, sv) = await Task.detached { (Engine.version(of: b), s.map { "\(Engine.version(of: $0)) (\(($0.path as NSString).abbreviatingWithTildeInPath))" } ?? "not found") }.value
            builtIn = b == nil ? "not in this build" : bv
            system = sv
        }
    }
}

/// `spliced` in a terminal, and for agents: a link at ~/.local/bin/spliced to the command inside the app.
enum CommandLineTool {
    static var link: URL { FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin/spliced") }

    struct Status { let label: String; let canInstall: Bool }

    static var status: Status {
        guard let own = Engine.bundled else { return Status(label: "Not in this build", canInstall: false) }
        let target = link.resolvingSymlinksInPath()
        if target.path == own.resolvingSymlinksInPath().path { return Status(label: "Installed at ~/.local/bin/spliced", canInstall: false) }
        if let other = Engine.system { return Status(label: "Already on this Mac at \((other.path as NSString).abbreviatingWithTildeInPath)", canInstall: false) }
        return Status(label: "Not installed", canInstall: true)
    }

    static func install() {
        guard let own = Engine.bundled else { return }
        let fm = FileManager.default
        do {
            try fm.createDirectory(at: link.deletingLastPathComponent(), withIntermediateDirectories: true)
            if (try? fm.destinationOfSymbolicLink(atPath: link.path)) != nil { try fm.removeItem(at: link) }
            try fm.createSymbolicLink(at: link, withDestinationURL: own)
            let onPath = (Engine.environment["PATH"] ?? "").split(separator: ":").contains { String($0) == link.deletingLastPathComponent().path }
            let a = NSAlert()
            a.messageText = "spliced is installed"
            a.informativeText = onPath ? "Open a new terminal window and type spliced." :
                "It is at ~/.local/bin/spliced, which isn't on your PATH yet. Add this line to ~/.zshrc, then open a new terminal window:\n\nexport PATH=\"$HOME/.local/bin:$PATH\""
            a.runModal()
        } catch {
            NSAlert(error: error).runModal()
        }
    }
}
