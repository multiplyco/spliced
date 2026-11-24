import AppKit
import WebKit

/// For screenshots in docs and checks, only when the app was started with SPLICED_DEBUG=1:
/// `swift scripts/snap.swift <out.png>` (or any distributed notification "co.multiply.spliced.snapshot" with the path
/// as its object) writes a picture of the front window. An app may always picture its own windows; a terminal may not.
enum Debug {
    static func install() {
        guard ProcessInfo.processInfo.environment["SPLICED_DEBUG"] == "1" else { return }
        DistributedNotificationCenter.default().addObserver(forName: .init("co.multiply.spliced.snapshot"), object: nil, queue: .main) { n in
            guard let path = n.object as? String else { return }
            if path.hasPrefix("hit:") { return hits(path) }
            path.hasSuffix(".txt") ? describe(to: URL(fileURLWithPath: path)) : snapshot(to: URL(fileURLWithPath: path))
        }
        DistributedNotificationCenter.default().addObserver(forName: .init("co.multiply.spliced.js"), object: nil, queue: .main) { n in
            guard let code = n.object as? String else { return }
            for w in NSApp.windows { if let c = w.windowController as? ProjectWindowController, w.isVisible { c.js(code) } }
        }
        // an item of the front project's menu of projects (the one under its name in the sidebar), by its title
        DistributedNotificationCenter.default().addObserver(forName: .init("co.multiply.spliced.menu"), object: nil, queue: .main) { n in
            guard let title = n.object as? String, let app = NSApp.delegate as? AppDelegate,
                  let c = NSApp.orderedWindows.lazy.compactMap({ $0.windowController as? ProjectWindowController }).first else { return }
            let m = app.projectMenu(for: c)
            if let i = m.items.firstIndex(where: { $0.title == title }) { m.performActionForItem(at: i) }
        }
    }

    /// The front window's words, buttons and checkboxes as text (for sheets and alerts, which draw on layers a snapshot can't see).
    static func describe(to url: URL) {
        var lines: [String] = ["dock badge: \(NSApp.dockTile.badgeLabel ?? "none")"]
        func walk(_ v: NSView) {
            if v.isHidden || v is WKWebView { return }
            if let b = v as? NSButton, !b.title.isEmpty {
                lines.append(b.allowsMixedState || b.bezelStyle == .regularSquare && b.image != nil ? "button \(b.title)" : (b.state == .on && (b.cell as? NSButtonCell)?.showsStateBy.contains(.contentsCellMask) == true ? "[x] " : "") + "button: \(b.title)\(b.isEnabled ? "" : " (off)")\(b.state == .on ? " (on)" : "")")
            } else if let t = v as? NSTextField, !t.stringValue.isEmpty {
                lines.append("text: \(t.stringValue)")
            }
            v.subviews.forEach(walk)
        }
        for w in NSApp.windows where w.isVisible {
            lines.append("window \(type(of: w)) \(w.title) \(Int(w.frame.width))x\(Int(w.frame.height))")
            if let root = w.contentView?.superview ?? w.contentView { walk(root) }
        }
        try? lines.joined(separator: "\n").write(to: url, atomically: true, encoding: .utf8)
    }

    /// "hit:x1,y1;x2,y2:<out.txt>": which view a click at each point (from the window's top left) would reach, and
    /// where the window's close button sits. For checking that the page still gets clicks in the old title bar.
    static func hits(_ spec: String) {
        let parts = spec.split(separator: ":", maxSplits: 2).map(String.init)
        guard parts.count == 3, let w = NSApp.orderedWindows.first(where: { $0.windowController is ProjectWindowController }),
              let frame = w.contentView?.superview else { return }
        var lines: [String] = []
        if let b = w.standardWindowButton(.closeButton), let sv = b.superview {
            let r = sv.convert(b.frame, to: nil)
            lines.append("close button: x \(Int(r.minX)) y-from-top \(Int(w.frame.height - r.maxY)) h \(Int(r.height))")
        }
        for p in parts[1].split(separator: ";") {
            let xy = p.split(separator: ",").compactMap { Double($0) }
            guard xy.count == 2 else { continue }
            let pt = NSPoint(x: xy[0], y: w.frame.height - xy[1])
            var v = frame.hitTest(frame.convert(pt, from: nil)), chain: [String] = []
            while let x = v, chain.count < 4 { chain.append(String(describing: type(of: x))); v = x.superview }
            lines.append("(\(Int(xy[0])), \(Int(xy[1]))): \(chain.joined(separator: " < "))")
        }
        try? lines.joined(separator: "\n").write(to: URL(fileURLWithPath: parts[2]), atomically: true, encoding: .utf8)
    }

    static func snapshot(to url: URL) {
        let w = NSApp.orderedWindows.first { $0.isVisible && $0.level == .normal }
        guard let w, let content = w.contentView else { return }
        if let web = content.subviews.compactMap({ $0 as? WKWebView }).first, (w.windowController as? ProjectWindowController) != nil,
           content.subviews.last?.isHidden ?? true {
            web.takeSnapshot(with: nil) { img, _ in
                guard let img else { return }
                // the traffic lights live above the page: draw them on, where they are
                if let close = w.standardWindowButton(.closeButton), let bar = close.superview {
                    let r = bar.convert(bar.bounds, to: nil)
                    if let rep = bar.bitmapImageRepForCachingDisplay(in: bar.bounds) {
                        bar.cacheDisplay(in: bar.bounds, to: rep)
                        img.lockFocus()
                        rep.draw(in: NSRect(x: r.minX, y: img.size.height - (w.frame.height - r.minY), width: r.width, height: r.height),
                                 from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
                        img.unlockFocus()
                    }
                }
                write(img, url)
            }
        } else {
            // an alert's frosted background doesn't draw off screen: paint the window's ground under its views
            let view = content.superview ?? content
            guard let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
            (w.appearance ?? NSApp.effectiveAppearance).performAsCurrentDrawingAppearance {
                NSColor.windowBackgroundColor.setFill()
                view.bounds.fill()
            }
            NSGraphicsContext.restoreGraphicsState()
            view.cacheDisplay(in: view.bounds, to: rep)
            let img = NSImage(size: view.bounds.size); img.addRepresentation(rep)
            write(img, url)
        }
    }

    private static func write(_ img: NSImage, _ url: URL) {
        guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else { return }
        try? png.write(to: url)
    }
}
