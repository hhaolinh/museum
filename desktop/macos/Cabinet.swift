import AppKit
import WebKit
import Sparkle

final class LocalServer {
    private var process: Process?
    private var log: FileHandle?
    private let lock = NSLock()
    private var buffer = Data()
    private var delivered = false
    private var expectedStop = false
    var onReady: ((Int) -> Void)?
    var onFailure: (() -> Void)?

    func start(dataDirectory: URL, token: String) throws {
        let executable = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/CabinetServer.app/Contents/MacOS/CabinetServer")
        let logs = dataDirectory.appendingPathComponent("logs", isDirectory: true)
        try FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
        let logURL = logs.appendingPathComponent("server.log")
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        log = try FileHandle(forWritingTo: logURL)
        try log?.seekToEnd()
        let task = Process()
        task.executableURL = executable
        var environment = ProcessInfo.processInfo.environment
        // Do not let a developer's Python environment alter the embedded interpreter.
        for key in ["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"] { environment.removeValue(forKey: key) }
        environment["CABINET_DATA_DIR"] = dataDirectory.path
        environment["CABINET_DESKTOP_TOKEN"] = token
        environment["CABINET_PARENT_PID"] = String(ProcessInfo.processInfo.processIdentifier)
        task.environment = environment
        task.currentDirectoryURL = dataDirectory
        let output = Pipe()
        task.standardOutput = output
        task.standardError = log
        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            guard let self = self else { return }
            let data = handle.availableData
            guard !data.isEmpty else { handle.readabilityHandler = nil; return }
            self.lock.lock()
            self.buffer.append(data)
            let lines = String(decoding: self.buffer, as: UTF8.self).split(separator: "\n")
            let line = lines.first(where: { $0.hasPrefix("CABINET_READY ") })
            let port = line.flatMap { Int($0.dropFirst("CABINET_READY ".count)) }
            let ready = !self.delivered && port != nil
            if ready { self.delivered = true }
            self.lock.unlock()
            if ready, let port = port, (1...65535).contains(port) {
                DispatchQueue.main.async { self.onReady?(port) }
            }
        }
        task.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, !self.expectedStop else { return }
                self.onFailure?()
            }
        }
        process = task
        try task.run()
    }

    func stop() {
        expectedStop = true
        process?.terminationHandler = nil
        if let task = process, task.isRunning {
            task.terminate()
            let deadline = Date().addingTimeInterval(2)
            while task.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.03) }
            if task.isRunning { kill(task.processIdentifier, SIGKILL) }
        }
        try? log?.close()
        process = nil
    }
    deinit { stop() }
}

@MainActor
final class CabinetDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, SPUUpdaterDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var loading: NSStackView!
    private var server: LocalServer?
    private var origin: URL?
    private var startupTimeout: Timer?
    private var failed = false
    private var updater: SPUStandardUpdaterController?
    private var automaticItem: NSMenuItem!
    private let dataDirectory: URL = {
        if let override = ProcessInfo.processInfo.environment["CABINET_TEST_DATA_DIR"] {
            return URL(fileURLWithPath: override, isDirectory: true)
        }
        return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Cabinet", isDirectory: true)
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        if installIfNeeded() { return }
        openCabinet()
    }

    private func installIfNeeded() -> Bool {
        if ProcessInfo.processInfo.environment["CABINET_SKIP_INSTALL"] == "1" { return false }
        let target = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications/Cabinet.app")
        if Bundle.main.bundleURL.standardizedFileURL == target.standardizedFileURL { return false }
        let installed = FileManager.default.fileExists(atPath: target.path)
        let alert = NSAlert()
        alert.messageText = installed ? "这台 Mac 已安装藏阁" : "将藏阁安装到这台 Mac"
        alert.informativeText = installed ? "打开已安装的应用，后续更新会在应用内完成。" : "安装后可从启动台打开，后续更新会自动完成。你的收藏将单独保存在这台 Mac 上。"
        alert.addButton(withTitle: installed ? "打开藏阁" : "安装并打开")
        alert.addButton(withTitle: "退出")
        NSApp.activate(ignoringOtherApps: true)
        guard alert.runModal() == .alertFirstButtonReturn else { NSApp.terminate(nil); return true }
        do {
            if !installed {
                try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
                try FileManager.default.copyItem(at: Bundle.main.bundleURL, to: target)
            }
            NSWorkspace.shared.openApplication(at: target, configuration: NSWorkspace.OpenConfiguration()) { _, error in
                DispatchQueue.main.async {
                    if let error = error { NSAlert(error: error).runModal() }
                    NSApp.terminate(nil)
                }
            }
        } catch {
            NSAlert(error: error).runModal()
            NSApp.terminate(nil)
        }
        return true
    }

    private func openCabinet() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.isHidden = true
        let content = NSView()
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor(red: 0.945, green: 0.933, blue: 0.902, alpha: 1).cgColor
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1240, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "藏阁 Cabinet"
        window.minSize = NSSize(width: 760, height: 560)
        window.contentView = content
        webView.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(webView)
        NSLayoutConstraint.activate([webView.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: content.trailingAnchor), webView.topAnchor.constraint(equalTo: content.topAnchor),
            webView.bottomAnchor.constraint(equalTo: content.bottomAnchor)])
        let spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.startAnimation(nil)
        let label = NSTextField(labelWithString: "正在打开藏阁…")
        label.textColor = .secondaryLabelColor
        loading = NSStackView(views: [spinner, label])
        loading.orientation = .vertical
        loading.spacing = 16
        loading.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(loading)
        NSLayoutConstraint.activate([loading.centerXAnchor.constraint(equalTo: content.centerXAnchor), loading.centerYAnchor.constraint(equalTo: content.centerYAnchor)])
        setupMenus()
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startServer()
    }

    private func startServer() {
        failed = false
        do {
            try FileManager.default.createDirectory(at: dataDirectory, withIntermediateDirectories: true,
                                                   attributes: [.posixPermissions: 0o700])
            let token = UUID().uuidString + UUID().uuidString
            let next = LocalServer()
            next.onReady = { [weak self] port in
                guard let self = self, !self.failed else { return }
                self.startupTimeout?.invalidate()
                self.origin = URL(string: "http://127.0.0.1:\(port)")!
                var url = URLComponents(url: self.origin!.appendingPathComponent("desktop/session"), resolvingAgainstBaseURL: false)!
                url.queryItems = [URLQueryItem(name: "token", value: token)]
                self.webView.load(URLRequest(url: url.url!))
            }
            next.onFailure = { [weak self] in self?.showStartupFailure() }
            server = next
            try next.start(dataDirectory: dataDirectory, token: token)
            startupTimeout = Timer.scheduledTimer(withTimeInterval: 30, repeats: false) { [weak self] _ in
                DispatchQueue.main.async { self?.showStartupFailure() }
            }
        } catch { showStartupFailure() }
    }

    private func showStartupFailure() {
        guard !failed else { return }
        failed = true
        startupTimeout?.invalidate()
        let alert = NSAlert()
        alert.messageText = "藏阁暂时没能打开"
        alert.informativeText = "你的收藏没有被清空。请重试；如果问题持续，可以从帮助菜单打开日志文件夹。"
        alert.addButton(withTitle: "重试")
        alert.addButton(withTitle: "退出")
        alert.beginSheetModal(for: window) { [weak self] response in
            guard let self = self else { return }
            if response == .alertFirstButtonReturn { self.server?.stop(); self.startServer() }
            else { NSApp.terminate(nil) }
        }
    }

    private func setupMenus() {
        let main = NSMenu()
        let appRoot = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "关于藏阁", action: #selector(about(_:)), keyEquivalent: "").target = self
        let check = appMenu.addItem(withTitle: "检查更新…", action: nil, keyEquivalent: "")
        automaticItem = appMenu.addItem(withTitle: "自动下载并安装更新", action: #selector(toggleAutomatic(_:)), keyEquivalent: "")
        automaticItem.target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "隐藏藏阁", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "退出藏阁", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appRoot.submenu = appMenu
        main.addItem(appRoot)
        let editRoot = NSMenuItem()
        let edit = NSMenu(title: "编辑")
        for (title, action, key) in [("撤销", Selector(("undo:")), "z"), ("剪切", #selector(NSText.cut(_:)), "x"),
                                    ("复制", #selector(NSText.copy(_:)), "c"), ("粘贴", #selector(NSText.paste(_:)), "v"),
                                    ("全选", #selector(NSText.selectAll(_:)), "a")] {
            edit.addItem(withTitle: title, action: action, keyEquivalent: key)
        }
        editRoot.submenu = edit; main.addItem(editRoot)
        let viewRoot = NSMenuItem()
        let view = NSMenu(title: "显示")
        view.addItem(withTitle: "返回", action: #selector(back(_:)), keyEquivalent: "[").target = self
        view.addItem(withTitle: "前进", action: #selector(forward(_:)), keyEquivalent: "]").target = self
        view.addItem(withTitle: "重新加载", action: #selector(reload(_:)), keyEquivalent: "r").target = self
        viewRoot.submenu = view; main.addItem(viewRoot)
        let helpRoot = NSMenuItem()
        let help = NSMenu(title: "帮助")
        help.addItem(withTitle: "打开收藏文件夹", action: #selector(showData(_:)), keyEquivalent: "").target = self
        help.addItem(withTitle: "打开日志文件夹", action: #selector(showLogs(_:)), keyEquivalent: "").target = self
        helpRoot.submenu = help; main.addItem(helpRoot)
        NSApp.mainMenu = main
        // Test feeds are only supplied by development/test builds, never by page content.
        updater = SPUStandardUpdaterController(startingUpdater: false, updaterDelegate: self, userDriverDelegate: nil)
        check.target = updater
        check.action = #selector(SPUStandardUpdaterController.checkForUpdates(_:))
        updater?.startUpdater()
        refreshAutomaticMenu()
        if updater?.updater.automaticallyChecksForUpdates == true { updater?.updater.checkForUpdatesInBackground() }
    }

    private func testEvent(_ value: String) {
        guard let path = ProcessInfo.processInfo.environment["CABINET_TEST_EVENTS"] else { return }
        let url = URL(fileURLWithPath: path)
        if !FileManager.default.fileExists(atPath: path) { FileManager.default.createFile(atPath: path, contents: nil) }
        if let file = try? FileHandle(forWritingTo: url) {
            try? file.seekToEnd()
            try? file.write(contentsOf: Data((value + "\n").utf8))
            try? file.close()
        }
    }
    func updater(_ updater: SPUUpdater, didDownloadUpdate item: SUAppcastItem) { testEvent("downloaded") }
    func updater(_ updater: SPUUpdater, willInstallUpdate item: SUAppcastItem) { testEvent("installing") }
    func updater(_ updater: SPUUpdater, willInstallUpdateOnQuit item: SUAppcastItem,
                 immediateInstallationBlock immediateInstallHandler: @escaping () -> Void) -> Bool {
        testEvent("ready-on-quit")
        return false
    }
    func updater(_ updater: SPUUpdater, didFinishUpdateCycleFor updateCheck: SPUUpdateCheck, error: Error?) {
        if let error = error { testEvent("update-error: " + error.localizedDescription) }
    }

    private func refreshAutomaticMenu() {
        automaticItem.state = updater?.updater.automaticallyChecksForUpdates == true && updater?.updater.automaticallyDownloadsUpdates == true ? .on : .off
    }
    @objc private func toggleAutomatic(_ sender: Any?) {
        guard let updater = updater?.updater else { return }
        let enabled = !(updater.automaticallyChecksForUpdates && updater.automaticallyDownloadsUpdates)
        updater.automaticallyChecksForUpdates = enabled
        updater.automaticallyDownloadsUpdates = enabled
        refreshAutomaticMenu()
    }
    @objc private func about(_ sender: Any?) { NSApp.orderFrontStandardAboutPanel(sender) }
    @objc private func back(_ sender: Any?) { webView.goBack() }
    @objc private func forward(_ sender: Any?) { webView.goForward() }
    @objc private func reload(_ sender: Any?) { webView.reload() }
    @objc private func showData(_ sender: Any?) { NSWorkspace.shared.open(dataDirectory) }
    @objc private func showLogs(_ sender: Any?) { NSWorkspace.shared.open(dataDirectory.appendingPathComponent("logs")) }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        loading.isHidden = true
        webView.isHidden = false
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { showStartupFailure() }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "about" { decisionHandler(.allow); return }
        if url.scheme == origin?.scheme && url.host == origin?.host && url.port == origin?.port {
            decisionHandler(.allow)
        } else {
            if ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.beginSheetModal(for: window) { response in completionHandler(response == .OK ? panel.urls : nil) }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) { startupTimeout?.invalidate(); server?.stop() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { window?.makeKeyAndOrderFront(nil) }; return true
    }
}

@main
struct CabinetMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.regular)
        let delegate = CabinetDelegate()
        app.delegate = delegate
        withExtendedLifetime(delegate) { app.run() }
    }
}
