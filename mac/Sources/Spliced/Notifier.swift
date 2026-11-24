import AppKit
import UserNotifications

/// A notification when something the person started finishes while they are elsewhere (an import, a folder).
/// When the project's window is in front, the page's own toast says it and this stays quiet. Clicking one brings
/// that project's window forward.
enum Notifier {
    static var onOpen: ((String) -> Void)?
    private static let delegate = Delegate()
    private static var asked = false

    static func post(title: String, body: String, project: URL, unlessLooking window: NSWindow?) {
        if NSApp.isActive, window?.isKeyWindow == true { return }
        let center = UNUserNotificationCenter.current()
        center.delegate = delegate
        let send = {
            let c = UNMutableNotificationContent()
            c.title = title
            c.body = body
            c.subtitle = Projects.name(project)
            c.userInfo = ["project": project.path]
            center.add(UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil))
        }
        if asked { return send() }
        center.requestAuthorization(options: [.alert, .sound]) { ok, _ in
            asked = true
            if ok { DispatchQueue.main.async(execute: send) }
        }
    }

    private final class Delegate: NSObject, UNUserNotificationCenterDelegate {
        func userNotificationCenter(_ c: UNUserNotificationCenter, didReceive r: UNNotificationResponse, withCompletionHandler done: @escaping () -> Void) {
            if let p = r.notification.request.content.userInfo["project"] as? String { DispatchQueue.main.async { Notifier.onOpen?(p); NSApp.activate(ignoringOtherApps: true) } }
            done()
        }
        func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification, withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) {
            done([.banner, .sound])
        }
    }
}
