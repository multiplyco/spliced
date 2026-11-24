// Ask a Spliced started with SPLICED_DEBUG=1 for a picture of its front window, or to run JavaScript in its pages:
//   swift mac/scripts/snap.swift <out.png>
//   swift mac/scripts/snap.swift --js "location.hash='#/setup'"
//   swift mac/scripts/snap.swift --menu "Close Project"   (an item of the front window's menu of projects)
import Foundation
let a = CommandLine.arguments
let (name, obj) = a.count > 2 && a[1] == "--js" ? ("co.multiply.spliced.js", a[2])
    : a.count > 2 && a[1] == "--menu" ? ("co.multiply.spliced.menu", a[2])
    : a.count > 3 && a[1] == "--hit" ? ("co.multiply.spliced.snapshot", "hit:\(a[2]):\(URL(fileURLWithPath: a[3]).path)")   // --hit "x,y;x,y" out.txt
    : ("co.multiply.spliced.snapshot", URL(fileURLWithPath: a[1]).path)
DistributedNotificationCenter.default().postNotificationName(.init(name), object: obj, userInfo: nil, deliverImmediately: true)
RunLoop.current.run(until: Date().addingTimeInterval(0.3))
