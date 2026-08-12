// Clack: the sound of a mechanical keyboard and of a mouse click,
// from the Mac menu bar.

import AppKit
import AVFoundation
import ServiceManagement

// MARK: - Sounds

/// The sounds of one pack: press, release, space bar.
/// Three variants of each, picked at random, so it does not sound robotic.
struct Voices {
    var down: [AVAudioPCMBuffer] = []
    var up: [AVAudioPCMBuffer] = []
    var space: [AVAudioPCMBuffer] = []
}

/// Every sound is loaded into memory at launch and the players run all the
/// time: when a key is pressed there is nothing left to do but play, hence the
/// near-zero latency.
final class SoundBank {
    private let engine = AVAudioEngine()
    private var players: [AVAudioPlayerNode] = []
    private var next = 0
    private var format: AVAudioFormat?
    private var level: Float = 0.7
    private(set) var packs: [String: Voices] = [:]

    /// How many sounds can overlap. Past twelve keystrokes in under a hundred
    /// milliseconds, nobody types that fast.
    private static let voiceCount = 12

    init(soundsDir: URL) {
        let dirs = (try? FileManager.default.contentsOfDirectory(
            at: soundsDir, includingPropertiesForKeys: [.isDirectoryKey])) ?? []
        for dir in dirs where (try? dir.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true {
            var voices = Voices()
            voices.down = load(dir, "down")
            voices.up = load(dir, "up")
            voices.space = load(dir, "space")
            if voices.space.isEmpty { voices.space = voices.down }
            if !voices.down.isEmpty { packs[dir.lastPathComponent] = voices }
        }
        format = packs.values.first?.down.first?.format
        buildGraph()
        // Plugging in headphones or switching audio output stops the engine:
        // without this, the app goes silent until the next launch.
        NotificationCenter.default.addObserver(
            forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main
        ) { [weak self] _ in self?.buildGraph() }
    }

    private func load(_ dir: URL, _ kind: String) -> [AVAudioPCMBuffer] {
        (1...3).compactMap { index in
            let url = dir.appendingPathComponent("\(kind)-\(index).wav")
            guard let file = try? AVAudioFile(forReading: url),
                  let buffer = AVAudioPCMBuffer(pcmFormat: file.processingFormat,
                                                frameCapacity: AVAudioFrameCount(file.length)),
                  (try? file.read(into: buffer)) != nil
            else { return nil }
            return buffer
        }
    }

    private func buildGraph() {
        guard let format else { return }
        engine.stop()
        players.forEach { engine.detach($0) }
        players = (0..<Self.voiceCount).map { _ in AVAudioPlayerNode() }
        for player in players {
            engine.attach(player)
            engine.connect(player, to: engine.mainMixerNode, format: format)
        }
        engine.mainMixerNode.outputVolume = level
        engine.prepare()
        try? engine.start()
        players.forEach { $0.play() }
    }

    var volume: Float {
        get { level }
        set {
            level = newValue
            engine.mainMixerNode.outputVolume = newValue
        }
    }

    func play(_ variants: [AVAudioPCMBuffer]) {
        guard engine.isRunning, let buffer = variants.randomElement() else { return }
        let player = players[next]
        next = (next + 1) % players.count
        player.volume = Float.random(in: 0.90...1.0)  // no two keystrokes sound alike
        player.scheduleBuffer(buffer, at: nil, options: .interrupts, completionHandler: nil)
        if !player.isPlaying { player.play() }
    }
}

// MARK: - Settings

enum Key {
    static let enabled = "enabled"
    static let mousePack = "mousePack"
    static let pack = "pack"
    static let volume = "volume"
}

/// The folders in Sounds/, in display order. A pack missing from disk simply
/// disappears from the menu.
let packOrder = [
    "thock", "clack", "felt", "typewriter", "cream",
    "marble", "spring", "laptop", "wood", "bubble",
]
let packNames = [
    "thock": "Thock, deep",
    "clack": "Clack, clacky",
    "felt": "Felt, quiet",
    "typewriter": "Typewriter",
    "cream": "Cream, soft and round",
    "marble": "Marble, bright and crisp",
    "spring": "Spring, IBM Model M",
    "laptop": "Laptop, flat and thin",
    "wood": "Wood, warm and hollow",
    "bubble": "Bubble, all pop",
]

let mouseOrder = [
    "mouse", "mouse-soft", "mouse-sharp", "mouse-heavy", "mouse-retro",
    "mouse-gaming", "mouse-tick", "mouse-clacky", "mouse-hollow", "mouse-trackpad",
]
let mouseNames = [
    "mouse": "Classic click",
    "mouse-soft": "Soft, muted",
    "mouse-sharp": "Dry and sharp",
    "mouse-heavy": "Heavy and deep",
    "mouse-retro": "Retro, ball mouse",
    "mouse-gaming": "Gaming, two-stage",
    "mouse-tick": "Tick, barely audible",
    "mouse-clacky": "Clacky",
    "mouse-hollow": "Hollow, thin shell",
    "mouse-trackpad": "Trackpad, dull",
]

// MARK: - Application

final class Controller: NSObject, NSMenuDelegate {
    private let defaults = UserDefaults.standard
    private let bank: SoundBank
    private let status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private var slider = NSSlider()
    private var permissionItem = NSMenuItem()
    private var loginItem = NSMenuItem()

    private var tap: CFMachPort?
    private var retry: Timer?
    private var lastFlags: UInt64 = 0
    private var voices = Voices()
    private var mouseVoices = Voices()

    /// Only the modifier-key bits matter to us: the rest of the flags change
    /// all the time and would make the app play sounds for nothing.
    private static let modifierMask = CGEventFlags([
        .maskAlphaShift, .maskShift, .maskControl,
        .maskAlternate, .maskCommand, .maskSecondaryFn,
    ]).rawValue

    override init() {
        defaults.register(defaults: [
            Key.enabled: true, Key.mousePack: "mouse", Key.pack: "thock", Key.volume: 0.7,
        ])
        // The sounds can be replaced without rebuilding the app by dropping
        // your own files into this folder.
        let override = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Clack/Sounds")
        let bundled = Bundle.main.resourceURL!.appendingPathComponent("Sounds")
        let dir = FileManager.default.fileExists(atPath: override.path) ? override : bundled
        bank = SoundBank(soundsDir: dir)
        super.init()

        guard !bank.packs.isEmpty else {
            alert("No sounds found", "No sound could be loaded from \(dir.path).")
            exit(1)
        }
        bank.volume = defaults.float(forKey: Key.volume)
        applyPack()
        buildMenu()
        refreshIcon()

        if !CGPreflightListenEventAccess() { CGRequestListenEventAccess() }
        startTap()
    }

    // MARK: Menu

    private func buildMenu() {
        menu.delegate = self
        add("Sounds enabled", #selector(toggleEnabled))
        menu.addItem(.separator())
        // Twenty sounds would sit badly in a flat menu: two submenus.
        addSubmenu("Keyboard", packOrder.filter { bank.packs[$0] != nil }
            .map { ($0, packNames[$0] ?? $0) }, currentPack, #selector(choosePack(_:)))
        addSubmenu("Mouse click", [("", "None")] + mouseOrder.filter { bank.packs[$0] != nil }
            .map { ($0, mouseNames[$0] ?? $0) }, currentMouse, #selector(chooseMouse(_:)))

        let row = NSView(frame: NSRect(x: 0, y: 0, width: 220, height: 30))
        slider = NSSlider(frame: NSRect(x: 22, y: 5, width: 176, height: 20))
        slider.minValue = 0
        slider.maxValue = 1
        slider.isContinuous = true
        slider.target = self
        slider.action = #selector(changeVolume(_:))
        row.addSubview(slider)
        let volumeItem = NSMenuItem()
        volumeItem.view = row
        menu.addItem(volumeItem)

        menu.addItem(.separator())
        loginItem = add("Open at login", #selector(toggleLogin))
        permissionItem = add("Allow in System Settings...", #selector(openSettings))
        menu.addItem(.separator())
        add("Quit Clack", #selector(quit))
        status.menu = menu
    }

    @discardableResult
    private func add(_ title: String, _ action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        menu.addItem(item)
        return item
    }

    /// A submenu of choices. It is its own delegate, otherwise the check marks
    /// would never be updated: menuNeedsUpdate only talks to the open menu.
    private func addSubmenu(_ title: String, _ choices: [(String, String)],
                            _ selected: String, _ action: Selector) {
        let sub = NSMenu()
        sub.delegate = self
        for (id, name) in choices {
            let item = NSMenuItem(title: name, action: action, keyEquivalent: "")
            item.target = self
            item.representedObject = id
            item.state = id == selected ? .on : .off  // check mark shown on first open
            sub.addItem(item)
        }
        let parent = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        parent.submenu = sub
        menu.addItem(parent)
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        let granted = CGPreflightListenEventAccess()
        for item in menu.items {
            switch item.action {
            case #selector(toggleEnabled): item.state = enabled ? .on : .off
            case #selector(choosePack(_:)):
                item.state = (item.representedObject as? String) == currentPack ? .on : .off
            case #selector(chooseMouse(_:)):
                item.state = (item.representedObject as? String) == currentMouse ? .on : .off
            default: break
            }
        }
        loginItem.state = SMAppService.mainApp.status == .enabled ? .on : .off
        // As long as permission is missing, the app hears nothing: say so.
        permissionItem.isHidden = granted && tap != nil
        slider.floatValue = bank.volume
    }

    // MARK: Actions

    private var enabled: Bool { defaults.bool(forKey: Key.enabled) }
    private var currentPack: String { defaults.string(forKey: Key.pack) ?? "thock" }
    /// Empty: the mouse stays silent.
    private var currentMouse: String { defaults.string(forKey: Key.mousePack) ?? "mouse" }

    @objc private func toggleEnabled() {
        defaults.set(!enabled, forKey: Key.enabled)
        refreshIcon()
    }

    @objc private func choosePack(_ sender: NSMenuItem) {
        guard let pack = sender.representedObject as? String else { return }
        defaults.set(pack, forKey: Key.pack)
        applyPack()
        bank.play(voices.down)  // instant preview
    }

    @objc private func chooseMouse(_ sender: NSMenuItem) {
        guard let pack = sender.representedObject as? String else { return }
        defaults.set(pack, forKey: Key.mousePack)
        applyPack()
        bank.play(mouseVoices.down)
    }

    @objc private func changeVolume(_ sender: NSSlider) {
        bank.volume = sender.floatValue
        defaults.set(sender.floatValue, forKey: Key.volume)
    }

    @objc private func toggleLogin() {
        if SMAppService.mainApp.status == .enabled {
            try? SMAppService.mainApp.unregister()
        } else {
            try? SMAppService.mainApp.register()
        }
    }

    @objc private func openSettings() {
        NSWorkspace.shared.open(URL(
            string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")!)
    }

    @objc private func quit() { NSApp.terminate(nil) }

    private func applyPack() {
        // Fall back to thock: bank.packs is unordered, taking "the first one"
        // could make the keyboard type with a mouse click.
        voices = bank.packs[currentPack] ?? bank.packs["thock"] ?? Voices()
        // Empty or unknown mouse pack: play() plays nothing, so silence.
        mouseVoices = bank.packs[currentMouse] ?? Voices()
    }

    private func refreshIcon() {
        status.button?.image = NSImage(systemSymbolName: "keyboard", accessibilityDescription: "Clack")
        status.button?.appearsDisabled = !enabled
    }

    private func alert(_ title: String, _ text: String) {
        let panel = NSAlert()
        panel.messageText = title
        panel.informativeText = text
        panel.runModal()
    }

    // MARK: Listening to the keyboard and the mouse

    private func startTap() {
        let mask: CGEventMask =
            (1 << CGEventType.keyDown.rawValue)
            | (1 << CGEventType.keyUp.rawValue)
            | (1 << CGEventType.flagsChanged.rawValue)
            | (1 << CGEventType.leftMouseDown.rawValue)
            | (1 << CGEventType.leftMouseUp.rawValue)
            | (1 << CGEventType.rightMouseDown.rawValue)
            | (1 << CGEventType.rightMouseUp.rawValue)
            | (1 << CGEventType.otherMouseDown.rawValue)
            | (1 << CGEventType.otherMouseUp.rawValue)

        guard let port = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,  // we listen, we never modify anything
            eventsOfInterest: mask,
            callback: { _, type, event, refcon in
                Unmanaged<Controller>.fromOpaque(refcon!).takeUnretainedValue().handle(type, event)
                return Unmanaged.passUnretained(event)
            },
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            // Permission not granted yet: keep retrying until it is.
            if retry == nil {
                NSLog("Clack: Input Monitoring permission missing")
                retry = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
                    self?.startTap()
                }
            }
            return
        }
        tap = port
        retry?.invalidate()
        retry = nil
        NSLog("Clack: listening")
        let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, port, 0)
        // commonModes: keys still sound while a menu is open.
        CFRunLoopAddSource(CFRunLoopGetMain(), source, .commonModes)
        CGEvent.tapEnable(tap: port, enable: true)
    }

    fileprivate func handle(_ type: CGEventType, _ event: CGEvent) {
        switch type {
        case .tapDisabledByTimeout, .tapDisabledByUserInput:
            // The system sometimes cuts the tap off: restart it, or it is silent for good.
            if let tap { CGEvent.tapEnable(tap: tap, enable: true) }

        case .keyDown:
            guard enabled else { return }
            guard event.getIntegerValueField(.keyboardEventAutorepeat) == 0 else { return }
            let code = event.getIntegerValueField(.keyboardEventKeycode)
            bank.play(code == 49 ? voices.space : voices.down)  // 49 = space bar

        case .keyUp:
            guard enabled else { return }
            bank.play(voices.up)

        case .flagsChanged:
            guard enabled else { return }
            let flags = event.flags.rawValue & Self.modifierMask
            // A bit turning on is a press, a bit turning off is a release.
            bank.play((flags & ~lastFlags) != 0 ? voices.down : voices.up)
            lastFlags = flags

        case .leftMouseDown, .rightMouseDown, .otherMouseDown:
            if enabled { bank.play(mouseVoices.down) }

        case .leftMouseUp, .rightMouseUp, .otherMouseUp:
            if enabled { bank.play(mouseVoices.up) }

        default:
            break
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // no Dock icon, no window
let controller = Controller()
app.run()
