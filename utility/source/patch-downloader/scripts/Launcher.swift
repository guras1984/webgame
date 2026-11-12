import Cocoa
import WebKit

@main
final class Launcher: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    private let process = Process()
    private let outputPipe = Pipe()
    private let errorPipe = Pipe()
    private var startupBuffer = Data()
    private var errorBuffer = Data()
    private var window: NSWindow!
    private var webView: WKWebView!
    private var isShuttingDown = false

    static func main() {
        let app = NSApplication.shared
        let delegate = Launcher()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeWindow()
        makeMenu()
        startServer()
    }

    private func makeWindow() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.loadHTMLString("""
        <!doctype html><html lang="ko"><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
        body{font:15px -apple-system,BlinkMacSystemFont,sans-serif;color:#354052;background:#f5f7fa;
        display:grid;place-items:center;height:90vh;margin:0}
        main{text-align:center;padding:28px}strong{font-size:18px}
        p{color:#718096}
        </style><main><strong>KJ Patch Downloader</strong>
        <p>다운로더를 시작하고 있습니다…</p></main></html>
        """, baseURL: nil)

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1080, height: 760),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "KJ Patch Downloader"
        window.minSize = NSSize(width: 820, height: 580)
        window.contentView = webView
        window.delegate = self
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    private func makeMenu() {
        let root = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "KJ Patch Downloader 종료", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        root.addItem(appItem)
        NSApplication.shared.mainMenu = root
    }

    private func startServer() {
        let resources = Bundle.main.resourceURL!
        process.executableURL = resources.appendingPathComponent("Runtime/bin/python3")
        process.arguments = [resources.appendingPathComponent("App/app.py").path, "--no-browser"]
        process.environment = ProcessInfo.processInfo.environment.merging(["PYTHONDONTWRITEBYTECODE": "1"]) { _, new in new }
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        outputPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty {
                handle.readabilityHandler = nil
                return
            }
            DispatchQueue.main.async { self?.consumeStartupOutput(data) }
        }
        errorPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty {
                handle.readabilityHandler = nil
                return
            }
            DispatchQueue.main.async { self?.appendErrorOutput(data) }
        }
        process.terminationHandler = { [weak self] task in
            DispatchQueue.main.async { self?.serverTerminated(task) }
        }

        do {
            try process.run()
        } catch {
            showError("프로그램을 시작하지 못했습니다.", detail: error.localizedDescription)
        }
    }

    private func consumeStartupOutput(_ data: Data) {
        startupBuffer.append(data)
        while let newline = startupBuffer.firstIndex(of: 10) {
            let lineData = Data(startupBuffer[..<newline])
            startupBuffer.removeSubrange(...newline)
            guard let line = String(data: lineData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
                  line.hasPrefix("http://127.0.0.1:"),
                  let url = URL(string: line),
                  url.host == "127.0.0.1",
                  url.port != nil else { continue }
            webView.load(URLRequest(url: url))
            return
        }
    }

    private func appendErrorOutput(_ data: Data) {
        errorBuffer.append(data)
        if errorBuffer.count > 16_384 {
            errorBuffer.removeSubrange(0..<(errorBuffer.count - 16_384))
        }
    }

    private func serverTerminated(_ task: Process) {
        outputPipe.fileHandleForReading.readabilityHandler = nil
        errorPipe.fileHandleForReading.readabilityHandler = nil
        if isShuttingDown { return }
        if task.terminationStatus != 0 {
            let detail = String(data: errorBuffer, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            showError("다운로더가 예기치 않게 종료되었습니다.", detail: detail.isEmpty ? "종료 코드: \(task.terminationStatus)" : detail)
        }
        NSApplication.shared.terminate(nil)
    }

    private func showError(_ message: String, detail: String) {
        let alert = NSAlert()
        alert.messageText = message
        alert.informativeText = detail
        alert.alertStyle = .critical
        alert.runModal()
        isShuttingDown = true
        if process.isRunning { process.terminate() }
        NSApplication.shared.terminate(nil)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if url.scheme == "http", url.host == "127.0.0.1" {
            decisionHandler(.allow)
            return
        }
        if ["http", "https"].contains(url.scheme ?? "") {
            NSWorkspace.shared.open(url)
        }
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, ["http", "https"].contains(url.scheme ?? "") {
            NSWorkspace.shared.open(url)
        }
        return nil
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        isShuttingDown = true
        if process.isRunning { process.terminate() }
        return true
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        isShuttingDown = true
        if process.isRunning { process.terminate() }
        return .terminateNow
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}