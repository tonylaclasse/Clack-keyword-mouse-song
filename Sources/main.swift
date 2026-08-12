// Clack : le bruit d'un clavier mecanique et d'un clic de souris,
// depuis la barre de menus du Mac.

import AppKit
import AVFoundation
import ServiceManagement

// MARK: - Sons

/// Les sons d'une ambiance : frappe, relachement, barre d'espace.
/// Trois variantes de chacun, tirees au hasard, pour ne pas sonner robotique.
struct Voices {
    var down: [AVAudioPCMBuffer] = []
    var up: [AVAudioPCMBuffer] = []
    var space: [AVAudioPCMBuffer] = []
}

/// Tous les sons sont charges en memoire au lancement et les lecteurs tournent
/// en permanence : au moment de la frappe il ne reste qu'a jouer, d'ou la
/// latence quasi nulle.
final class SoundBank {
    private let engine = AVAudioEngine()
    private var players: [AVAudioPlayerNode] = []
    private var next = 0
    private var format: AVAudioFormat?
    private var level: Float = 0.7
    private(set) var packs: [String: Voices] = [:]

    /// Nombre de sons pouvant se chevaucher. Au-dela de douze frappes en moins
    /// de cent millisecondes, plus personne ne tape aussi vite.
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
        // Brancher un casque ou changer de sortie audio arrete le moteur :
        // sans ca, l'app devient muette jusqu'au prochain lancement.
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
        player.volume = Float.random(in: 0.90...1.0)  // deux frappes ne sonnent jamais pareil
        player.scheduleBuffer(buffer, at: nil, options: .interrupts, completionHandler: nil)
        if !player.isPlaying { player.play() }
    }
}

// MARK: - Reglages

enum Key {
    static let enabled = "enabled"
    static let mouse = "mouse"
    static let pack = "pack"
    static let volume = "volume"
}

let packOrder = ["thock", "clack", "feutre", "machine"]
let packNames = [
    "thock": "Thock, profond",
    "clack": "Clack, claquant",
    "feutre": "Feutre, discret",
    "machine": "Machine a ecrire",
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

    /// Seuls les bits des touches de modification nous interessent : le reste
    /// des indicateurs change tout le temps et ferait sonner dans le vide.
    private static let modifierMask = CGEventFlags([
        .maskAlphaShift, .maskShift, .maskControl,
        .maskAlternate, .maskCommand, .maskSecondaryFn,
    ]).rawValue

    override init() {
        defaults.register(defaults: [
            Key.enabled: true, Key.mouse: true, Key.pack: "thock", Key.volume: 0.7,
        ])
        // Les sons peuvent etre remplaces sans reconstruire l'app en deposant
        // ses propres fichiers dans ce dossier.
        let override = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Clack/Sounds")
        let bundled = Bundle.main.resourceURL!.appendingPathComponent("Sounds")
        let dir = FileManager.default.fileExists(atPath: override.path) ? override : bundled
        bank = SoundBank(soundsDir: dir)
        super.init()

        guard !bank.packs.isEmpty else {
            alert("Sons introuvables", "Aucun son n'a pu etre charge depuis \(dir.path).")
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
        add("Sons actives", #selector(toggleEnabled))
        menu.addItem(.separator())
        for pack in packOrder where bank.packs[pack] != nil {
            add(packNames[pack] ?? pack, #selector(choosePack(_:))).representedObject = pack
        }
        menu.addItem(.separator())
        add("Clic de souris", #selector(toggleMouse))

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
        loginItem = add("Lancer au demarrage", #selector(toggleLogin))
        permissionItem = add("Autoriser dans Reglages Systeme...", #selector(openSettings))
        menu.addItem(.separator())
        add("Quitter Clack", #selector(quit))
        status.menu = menu
    }

    @discardableResult
    private func add(_ title: String, _ action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        menu.addItem(item)
        return item
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        let granted = CGPreflightListenEventAccess()
        for item in menu.items {
            switch item.action {
            case #selector(toggleEnabled): item.state = enabled ? .on : .off
            case #selector(toggleMouse): item.state = defaults.bool(forKey: Key.mouse) ? .on : .off
            case #selector(choosePack(_:)):
                item.state = (item.representedObject as? String) == currentPack ? .on : .off
            default: break
            }
        }
        loginItem.state = SMAppService.mainApp.status == .enabled ? .on : .off
        // Tant que l'autorisation manque, l'app n'entend rien : on le dit.
        permissionItem.isHidden = granted && tap != nil
        slider.floatValue = bank.volume
    }

    // MARK: Actions

    private var enabled: Bool { defaults.bool(forKey: Key.enabled) }
    private var currentPack: String { defaults.string(forKey: Key.pack) ?? "thock" }

    @objc private func toggleEnabled() {
        defaults.set(!enabled, forKey: Key.enabled)
        refreshIcon()
    }

    @objc private func toggleMouse() {
        defaults.set(!defaults.bool(forKey: Key.mouse), forKey: Key.mouse)
    }

    @objc private func choosePack(_ sender: NSMenuItem) {
        guard let pack = sender.representedObject as? String else { return }
        defaults.set(pack, forKey: Key.pack)
        applyPack()
        bank.play(voices.down)  // apercu immediat
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
        voices = bank.packs[currentPack] ?? bank.packs.values.first ?? Voices()
        mouseVoices = bank.packs["mouse"] ?? Voices()
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

    // MARK: Ecoute du clavier et de la souris

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
            options: .listenOnly,  // on ecoute, on ne modifie jamais rien
            eventsOfInterest: mask,
            callback: { _, type, event, refcon in
                Unmanaged<Controller>.fromOpaque(refcon!).takeUnretainedValue().handle(type, event)
                return Unmanaged.passUnretained(event)
            },
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            // Autorisation pas encore accordee : on retente jusqu'a ce qu'elle le soit.
            if retry == nil {
                NSLog("Clack : autorisation Surveillance de la saisie manquante")
                retry = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
                    self?.startTap()
                }
            }
            return
        }
        tap = port
        retry?.invalidate()
        retry = nil
        NSLog("Clack : ecoute active")
        let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, port, 0)
        // commonModes : les touches sonnent aussi pendant qu'un menu est ouvert.
        CFRunLoopAddSource(CFRunLoopGetMain(), source, .commonModes)
        CGEvent.tapEnable(tap: port, enable: true)
    }

    fileprivate func handle(_ type: CGEventType, _ event: CGEvent) {
        switch type {
        case .tapDisabledByTimeout, .tapDisabledByUserInput:
            // Le systeme coupe parfois l'ecoute : la relancer, sinon silence definitif.
            if let tap { CGEvent.tapEnable(tap: tap, enable: true) }

        case .keyDown:
            guard enabled else { return }
            guard event.getIntegerValueField(.keyboardEventAutorepeat) == 0 else { return }
            let code = event.getIntegerValueField(.keyboardEventKeycode)
            bank.play(code == 49 ? voices.space : voices.down)  // 49 = barre d'espace

        case .keyUp:
            guard enabled else { return }
            bank.play(voices.up)

        case .flagsChanged:
            guard enabled else { return }
            let flags = event.flags.rawValue & Self.modifierMask
            // Un bit qui s'allume est un appui, un bit qui s'eteint un relachement.
            bank.play((flags & ~lastFlags) != 0 ? voices.down : voices.up)
            lastFlags = flags

        case .leftMouseDown, .rightMouseDown, .otherMouseDown:
            if enabled, defaults.bool(forKey: Key.mouse) { bank.play(mouseVoices.down) }

        case .leftMouseUp, .rightMouseUp, .otherMouseUp:
            if enabled, defaults.bool(forKey: Key.mouse) { bank.play(mouseVoices.up) }

        default:
            break
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // pas d'icone dans le Dock, pas de fenetre
let controller = Controller()
app.run()
