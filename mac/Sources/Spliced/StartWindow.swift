import AppKit
import SwiftUI

/// The window with no project open yet: recent projects, open one, make a new one.
final class StartWindowController: NSWindowController {
    convenience init(open: @escaping (URL) -> Void, newProject: @escaping () -> Void, openPanel: @escaping () -> Void) {
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 720, height: 440),
                           styleMask: [.titled, .closable, .fullSizeContentView], backing: .buffered, defer: false)
        win.titlebarAppearsTransparent = true
        win.titleVisibility = .hidden
        win.isMovableByWindowBackground = true
        win.title = "Spliced"
        win.appearance = NSAppearance(named: .darkAqua)   // Spliced is dark by default, like the app's page
        win.contentView = NSHostingView(rootView: StartView(open: open, newProject: newProject, openPanel: openPanel))
        win.center()
        self.init(window: win)
    }
}

private let ink = Color(red: 0.043, green: 0.043, blue: 0.047)
private let panel = Color(red: 0.086, green: 0.086, blue: 0.094)
private let volt = Color(red: 0xDF / 255, green: 1, blue: 0x1A / 255)

struct StartView: View {
    let open: (URL) -> Void
    let newProject: () -> Void
    let openPanel: () -> Void
    @State private var recents = Projects.recents
    @State private var selection: URL?
    @State private var update = Updates.shared.available

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 0) {
                Logo().frame(width: 64, height: 64)
                Text("Spliced").font(.system(size: 26, weight: .semibold)).foregroundColor(.white).padding(.top, 18)
                Text("Version \(Bundle.main.shortVersion)").font(.system(size: 12)).foregroundColor(.white.opacity(0.45)).padding(.top, 2)
                if let u = update {
                    Button(Updates.shared.checkout != nil ? "\(u.version): update app" : "Version \(u.version) is out: update app") { Updates.shared.install() }
                        .buttonStyle(.plain).font(.system(size: 12, weight: .medium)).foregroundColor(volt).padding(.top, 4)
                        .help(u.detail)
                }
                Text("Study the films you love scene by scene, and make your own with your AI.")
                    .font(.system(size: 13)).foregroundColor(.white.opacity(0.7)).fixedSize(horizontal: false, vertical: true).padding(.top, 14)
                Spacer()
                VStack(alignment: .leading, spacing: 8) {
                    StartButton(title: "New project…", detail: "A folder for your library and films", primary: true, action: newProject)
                    StartButton(title: "Open a project…", detail: "A folder with a spliced.json", primary: false, action: openPanel)
                }
            }
            .padding(32)
            .frame(width: 300)
            .frame(maxHeight: .infinity)
            .background(ink)

            VStack(alignment: .leading, spacing: 0) {
                Text("Recent").font(.system(size: 12, weight: .semibold)).foregroundColor(.white.opacity(0.45))
                    .padding(.horizontal, 20).padding(.top, 40).padding(.bottom, 8)
                if recents.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("No projects yet.").font(.system(size: 13)).foregroundColor(.white)
                        Text("Make a new one, or open a folder that already is one. You can also drop a project folder on Spliced in the Dock.")
                            .font(.system(size: 12)).foregroundColor(.white.opacity(0.55)).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.horizontal, 20)
                    Spacer()
                } else {
                    ScrollView {
                        VStack(spacing: 2) {
                            ForEach(recents, id: \.self) { url in
                                RecentRow(url: url, selected: selection == url)
                                    .onTapGesture(count: 2) { open(url) }
                                    .simultaneousGesture(TapGesture().onEnded { selection = url })
                                    .contextMenu {
                                        Button("Open") { open(url) }
                                        Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([url]) }
                                        Divider()
                                        Button("Remove from Recent") { Projects.forget(url) }
                                    }
                            }
                        }
                        .padding(.horizontal, 10)
                    }
                    HStack {
                        Text("Double-click to open").font(.system(size: 11)).foregroundColor(.white.opacity(0.35))
                        Spacer()
                        Button("Open") { if let s = selection { open(s) } }.disabled(selection == nil).keyboardShortcut(.defaultAction)
                    }
                    .padding(14)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(panel)
        }
        .frame(width: 720, height: 440)
        .onReceive(NotificationCenter.default.publisher(for: .recentsChanged)) { _ in recents = Projects.recents }
        .onReceive(NotificationCenter.default.publisher(for: .updateChanged)) { _ in update = Updates.shared.available }
    }
}

private struct RecentRow: View {
    let url: URL
    let selected: Bool
    @State private var hover = false

    var body: some View {
        let here = Projects.isProject(url)
        HStack(spacing: 10) {
            Image(systemName: here ? "film.stack" : "questionmark.folder").foregroundColor(.white.opacity(here ? 0.8 : 0.4)).frame(width: 18)
            VStack(alignment: .leading, spacing: 1) {
                Text(here ? Projects.name(url) : url.lastPathComponent).font(.system(size: 13, weight: .medium)).foregroundColor(.white)
                Text(here ? (url.path as NSString).abbreviatingWithTildeInPath : "Not found at \((url.path as NSString).abbreviatingWithTildeInPath)")
                    .font(.system(size: 11)).foregroundColor(.white.opacity(0.45)).lineLimit(1).truncationMode(.middle)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10).padding(.vertical, 7)
        .background(RoundedRectangle(cornerRadius: 7).fill(Color.white.opacity(selected ? 0.12 : hover ? 0.06 : 0)))
        .contentShape(Rectangle())
        .opacity(here ? 1 : 0.6)
        .onHover { hover = $0 }
    }
}

private struct StartButton: View {
    let title: String
    let detail: String
    let primary: Bool
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.system(size: 13, weight: .semibold)).foregroundColor(primary ? ink : .white)
                Text(detail).font(.system(size: 11)).foregroundColor(primary ? ink.opacity(0.7) : .white.opacity(0.5))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(RoundedRectangle(cornerRadius: 8).fill(primary ? volt.opacity(hover ? 0.9 : 1) : Color.white.opacity(hover ? 0.12 : 0.07)))
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
    }
}
