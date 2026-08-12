// Verifie hors ligne que la chaine audio de Clack sort vraiment du son :
// chargement du WAV, branchement du lecteur au mixeur, lecture d'un tampon.
import AVFoundation

let dir = URL(fileURLWithPath: "/Applications/Clack.app/Contents/Resources/Sounds/thock")
let file = try AVAudioFile(forReading: dir.appendingPathComponent("down-1.wav"))
let buffer = AVAudioPCMBuffer(pcmFormat: file.processingFormat,
                              frameCapacity: AVAudioFrameCount(file.length))!
try file.read(into: buffer)
print("fichier : \(file.processingFormat.sampleRate) Hz, \(buffer.frameLength) echantillons")

let engine = AVAudioEngine()
let player = AVAudioPlayerNode()
engine.attach(player)
engine.connect(player, to: engine.mainMixerNode, format: file.processingFormat)

let out = AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 2)!
try engine.enableManualRenderingMode(.offline, format: out, maximumFrameCount: 4096)
try engine.start()
player.play()
player.scheduleBuffer(buffer, at: nil, options: .interrupts, completionHandler: nil)

let render = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: 4096)!
var peak: Float = 0
var frames = 0
while frames < 9600 {  // 200 ms
    guard try engine.renderOffline(4096, to: render) == .success else { break }
    let channel = render.floatChannelData![0]
    for i in 0..<Int(render.frameLength) { peak = max(peak, abs(channel[i])) }
    frames += Int(render.frameLength)
}
print("pic en sortie du mixeur : \(peak)")
assert(peak > 0.05, "le moteur audio ne produit rien")
print("OK : la chaine audio sort du son")
