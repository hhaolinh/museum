import AppKit
let target = CommandLine.arguments[1]
let image = NSImage(size: NSSize(width: 1024, height: 1024))
image.lockFocus()
NSColor(red: 0.945, green: 0.933, blue: 0.902, alpha: 1).setFill()
NSBezierPath(roundedRect: NSRect(x: 35, y: 35, width: 954, height: 954), xRadius: 212, yRadius: 212).fill()
NSColor(red: 0.137, green: 0.298, blue: 0.235, alpha: 1).setFill()
NSBezierPath(ovalIn: NSRect(x: 200, y: 200, width: 624, height: 624)).fill()
let text = "藏" as NSString
let style = NSMutableParagraphStyle()
style.alignment = .center
let font = NSFont(name: "Songti SC", size: 410) ?? NSFont.systemFont(ofSize: 410)
text.draw(in: NSRect(x: 200, y: 252, width: 624, height: 510), withAttributes: [.font: font, .foregroundColor: NSColor(red: 0.945, green: 0.933, blue: 0.902, alpha: 1), .paragraphStyle: style])
image.unlockFocus()
let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
try rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: target))
