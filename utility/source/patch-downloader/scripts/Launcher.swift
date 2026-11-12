import Cocoa

@main
final class Launcher: NSObject, NSApplicationDelegate {
    let process = Process()
    var window: NSWindow!
    static func main() {
        let app = NSApplication.shared
        let delegate = Launcher()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        let resources = Bundle.main.resourceURL!
        process.executableURL = resources.appendingPathComponent("Runtime/bin/python3")
        process.arguments = [resources.appendingPathComponent("App/app.py").path]
        process.environment = ProcessInfo.processInfo.environment.merging(["PYTHONDONTWRITEBYTECODE":"1"]) { _, new in new }
        process.terminationHandler = { _ in DispatchQueue.main.async { NSApplication.shared.terminate(nil) } }
        do { try process.run() } catch {
            let alert = NSAlert(); alert.messageText = "KJ Patch Downloader 실행 오류"; alert.informativeText = error.localizedDescription; alert.runModal(); NSApplication.shared.terminate(nil); return
        }
        let menu = NSMenu(); let item = NSMenuItem(); menu.addItem(item)
        let appMenu = NSMenu(); appMenu.addItem(withTitle: "KJ Patch Downloader 종료", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"); item.submenu = appMenu; NSApplication.shared.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x:0,y:0,width:430,height:180), styleMask:[.titled,.closable,.miniaturizable], backing:.buffered, defer:false)
        window.title = "KJ Patch Downloader"
        let label = NSTextField(wrappingLabelWithString:"브라우저에서 패치 다운로드 화면을 열었습니다.\n다운로드하는 동안 앱을 실행해 두세요.\n화면의 ‘앱 종료’ 또는 ⌘Q로 종료할 수 있습니다.")
        label.frame = NSRect(x:25,y:40,width:380,height:100); label.font = .systemFont(ofSize:14); window.contentView?.addSubview(label)
        window.center(); window.makeKeyAndOrderFront(nil)
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if process.isRunning { process.terminate() }
        return .terminateNow
    }
}
