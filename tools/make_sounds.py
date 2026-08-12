#!/usr/bin/env python3
"""Build Clack's sounds (16-bit mono 48 kHz WAV).

No dependencies: standard library only.
The sounds are synthesised, so they are royalty-free and editable right here.

Recipe for a click: a very short burst of noise (the plastic contact) laid
over damped sine waves (the resonance of the case).

    python3 tools/make_sounds.py          # generates Sounds/
    python3 tools/make_sounds.py --check  # checks what was generated
"""

import itertools
import math
import os
import random
import struct
import sys
import wave

SR = 48000
VARIANTS = 3  # three versions of every sound, picked at random on each key
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Sounds")

# --- synthesis building blocks -----------------------------------------------


def lowpass(x, fc):
    """One-pole low-pass filter: cuts the highs above fc."""
    a = 1.0 - math.exp(-2.0 * math.pi * fc / SR)
    y = 0.0
    out = []
    for v in x:
        y += a * (v - y)
        out.append(y)
    return out


def highpass(x, fc):
    """One-pole high-pass filter: the signal minus its lows."""
    lp = lowpass(x, fc)
    return [v - l for v, l in zip(x, lp)]


def burst(buf, rng, amp, tau, hp, lp, offset=0.0):
    """Filtered burst of noise, decaying exponentially."""
    n = min(int(tau * 12 * SR) + 8, len(buf))
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    noise = lowpass(highpass(noise, hp), lp)
    start = int(offset * SR)
    for i, v in enumerate(noise):
        j = start + i
        if j >= len(buf):
            break
        buf[j] += amp * v * math.exp(-i / (tau * SR))


def body(buf, freq, amp, tau, offset=0.0):
    """Damped sine wave: the resonance of the case or of the key.

    The offset is there for two-stage sounds, like the spring that snaps then
    sings a fraction of a millisecond later.
    """
    start = int(offset * SR)
    n = min(int(tau * 9 * SR) + 8, len(buf) - start)
    w = 2.0 * math.pi * freq / SR
    for i in range(n):
        buf[start + i] += amp * math.exp(-i / (tau * SR)) * math.sin(w * i)


def render(spec, seed):
    rng = random.Random(seed)
    buf = [0.0] * int(spec["dur"] * SR)
    for b in spec["bursts"]:
        burst(buf, rng, *b)
    # each variant detunes the resonance slightly: avoids the robot effect
    for freq, amp, tau, *rest in spec["body"]:
        body(buf, freq * rng.uniform(0.96, 1.04), amp * rng.uniform(0.92, 1.06), tau,
             rest[0] if rest else 0.0)
    fade(buf)
    return buf


def fade(buf):
    """Very short ramps at both ends so the sound does not pop."""
    n_in, n_out = int(0.0002 * SR), int(0.002 * SR)
    for i in range(min(n_in, len(buf))):
        buf[i] *= i / n_in
    for i in range(min(n_out, len(buf))):
        buf[len(buf) - 1 - i] *= i / n_out


def write_wav(path, samples):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32000)) for v in samples
        )
        w.writeframes(frames)


# --- the sound packs ---------------------------------------------------------
# bursts: (amplitude, decay time, high-pass cutoff, low-pass cutoff, offset)
# body  : (frequency, amplitude, decay time, offset)
# A pack whose name starts with "mouse" is a mouse click: no space bar, and the
# app offers it in a separate menu.

PACKS = {
    # deep and damped, like a modern foam-filled keyboard
    "thock": {
        "gain": 0.82,
        "down": {
            "dur": 0.090,
            "bursts": [(0.50, 0.0012, 200, 4500)],
            "body": [(170, 0.85, 0.020), (330, 0.30, 0.012), (95, 0.50, 0.028)],
        },
        "up": {
            "dur": 0.050,
            "bursts": [(0.28, 0.0009, 300, 6000)],
            "body": [(215, 0.45, 0.011)],
        },
        "space": {
            "dur": 0.120,
            "bursts": [(0.62, 0.0018, 150, 3800)],
            "body": [(115, 1.00, 0.030), (225, 0.35, 0.018), (72, 0.50, 0.035)],
        },
    },
    # dry and bright, like a clicky switch
    "clack": {
        "gain": 0.90,
        "down": {
            "dur": 0.055,
            "bursts": [(0.85, 0.0007, 900, 12000), (0.50, 0.0005, 1500, 14000, 0.0035)],
            "body": [(1250, 0.35, 0.006), (2600, 0.25, 0.004), (420, 0.30, 0.010)],
        },
        "up": {
            "dur": 0.035,
            "bursts": [(0.50, 0.0005, 1200, 13000)],
            "body": [(1900, 0.20, 0.004)],
        },
        "space": {
            "dur": 0.070,
            "bursts": [(0.90, 0.0009, 700, 11000), (0.55, 0.0006, 1300, 13000, 0.0040)],
            "body": [(900, 0.40, 0.008), (300, 0.45, 0.014)],
        },
    },
    # quiet, usable in an open-plan office
    "felt": {
        "gain": 0.48,
        "down": {
            "dur": 0.070,
            "bursts": [(0.35, 0.0018, 120, 2200)],
            "body": [(125, 0.60, 0.022), (240, 0.18, 0.010)],
        },
        "up": {
            "dur": 0.040,
            "bursts": [(0.18, 0.0012, 180, 2600)],
            "body": [(160, 0.30, 0.010)],
        },
        "space": {
            "dur": 0.090,
            "bursts": [(0.45, 0.0024, 90, 1800)],
            "body": [(88, 0.80, 0.030)],
        },
    },
    # metallic and resonant, like a typewriter
    "typewriter": {
        "gain": 0.85,
        "down": {
            "dur": 0.140,
            "bursts": [(0.70, 0.0009, 1200, 15000)],
            "body": [
                (1850, 0.35, 0.030),
                (2740, 0.25, 0.022),
                (4100, 0.15, 0.016),
                (95, 0.60, 0.035),
            ],
        },
        "up": {
            "dur": 0.050,
            "bursts": [(0.30, 0.0006, 1500, 14000)],
            "body": [(2300, 0.18, 0.012), (140, 0.20, 0.016)],
        },
        "space": {
            "dur": 0.160,
            "bursts": [(0.75, 0.0010, 1000, 14000)],
            "body": [(70, 0.90, 0.050), (1600, 0.30, 0.030), (2500, 0.15, 0.020)],
        },
    },
    # round and soft, like a lubed linear switch
    "cream": {
        "gain": 0.78,
        "down": {
            "dur": 0.075,
            "bursts": [(0.42, 0.0010, 250, 5500)],
            "body": [(240, 0.80, 0.016), (470, 0.28, 0.009), (130, 0.35, 0.022)],
        },
        "up": {
            "dur": 0.045,
            "bursts": [(0.24, 0.0008, 350, 6500)],
            "body": [(300, 0.40, 0.009)],
        },
        "space": {
            "dur": 0.100,
            "bursts": [(0.55, 0.0014, 180, 4800)],
            "body": [(160, 0.95, 0.024), (310, 0.30, 0.014)],
        },
    },
    # bright and crisp, the "pock" of a keyboard with a rigid plate
    "marble": {
        "gain": 0.80,
        "down": {
            "dur": 0.060,
            "bursts": [(0.60, 0.0008, 500, 9000)],
            "body": [(760, 0.55, 0.010), (1450, 0.22, 0.006), (380, 0.30, 0.014)],
        },
        "up": {
            "dur": 0.035,
            "bursts": [(0.32, 0.0006, 700, 9500)],
            "body": [(980, 0.25, 0.006)],
        },
        "space": {
            "dur": 0.085,
            "bursts": [(0.68, 0.0012, 380, 8000)],
            "body": [(520, 0.65, 0.016), (250, 0.35, 0.020)],
        },
    },
    # the snap then the song of the spring, like an IBM Model M
    "spring": {
        "gain": 0.88,
        "down": {
            "dur": 0.200,
            "bursts": [(0.80, 0.0006, 1500, 14000)],
            "body": [
                (3200, 0.30, 0.045, 0.0020),
                (4700, 0.18, 0.035, 0.0020),
                (1900, 0.22, 0.030, 0.0030),
                (180, 0.45, 0.020),
            ],
        },
        "up": {
            "dur": 0.060,
            "bursts": [(0.35, 0.0005, 1600, 14000)],
            "body": [(2600, 0.20, 0.012), (200, 0.20, 0.014)],
        },
        "space": {
            "dur": 0.220,
            "bursts": [(0.85, 0.0008, 1200, 13000)],
            "body": [
                (2400, 0.30, 0.050, 0.0020),
                (3600, 0.18, 0.040, 0.0020),
                (110, 0.55, 0.030),
            ],
        },
    },
    # flat and thin, a laptop keyboard
    "laptop": {
        "gain": 0.62,
        "down": {
            "dur": 0.040,
            "bursts": [(0.55, 0.0006, 700, 8500)],
            "body": [(620, 0.35, 0.006), (1100, 0.20, 0.004)],
        },
        "up": {
            "dur": 0.028,
            "bursts": [(0.30, 0.0004, 900, 9000)],
            "body": [(880, 0.18, 0.003)],
        },
        "space": {
            "dur": 0.055,
            "bursts": [(0.62, 0.0008, 500, 7500)],
            "body": [(430, 0.45, 0.009), (210, 0.25, 0.012)],
        },
    },
    # warm and hollow, a wooden case
    "wood": {
        "gain": 0.80,
        "down": {
            "dur": 0.110,
            "bursts": [(0.45, 0.0014, 160, 3500)],
            "body": [(300, 0.70, 0.028), (600, 0.25, 0.016), (150, 0.45, 0.034)],
        },
        "up": {
            "dur": 0.050,
            "bursts": [(0.25, 0.0010, 240, 4200)],
            "body": [(380, 0.35, 0.014)],
        },
        "space": {
            "dur": 0.130,
            "bursts": [(0.55, 0.0020, 120, 3000)],
            "body": [(200, 0.90, 0.038), (400, 0.30, 0.022)],
        },
    },
    # almost no contact noise: a bubble popping
    "bubble": {
        "gain": 0.72,
        "down": {
            "dur": 0.050,
            "bursts": [(0.22, 0.0005, 400, 7000)],
            "body": [(560, 0.95, 0.008), (1120, 0.20, 0.004)],
        },
        "up": {
            "dur": 0.030,
            "bursts": [(0.14, 0.0004, 500, 7500)],
            "body": [(760, 0.45, 0.005)],
        },
        "space": {
            "dur": 0.070,
            "bursts": [(0.28, 0.0007, 300, 6000)],
            "body": [(360, 1.00, 0.012), (720, 0.22, 0.006)],
        },
    },
    # --- the mouse clicks: very short, no space bar ---------------------------
    # the classic click
    "mouse": {
        "gain": 0.75,
        "down": {
            "dur": 0.030,
            "bursts": [(0.70, 0.0006, 800, 11000)],
            "body": [(1500, 0.30, 0.004), (600, 0.25, 0.007)],
        },
        "up": {
            "dur": 0.022,
            "bursts": [(0.45, 0.0004, 1100, 12000)],
            "body": [(2000, 0.20, 0.003)],
        },
    },
    # muted, for working next to someone
    "mouse-soft": {
        "gain": 0.55,
        "down": {
            "dur": 0.026,
            "bursts": [(0.40, 0.0008, 300, 4000)],
            "body": [(700, 0.25, 0.005), (320, 0.20, 0.008)],
        },
        "up": {
            "dur": 0.018,
            "bursts": [(0.25, 0.0005, 400, 4500)],
            "body": [(900, 0.15, 0.003)],
        },
    },
    # dry and sharp, almost a pen click
    "mouse-sharp": {
        "gain": 0.80,
        "down": {
            "dur": 0.022,
            "bursts": [(0.85, 0.0004, 1800, 15000)],
            "body": [(2600, 0.25, 0.003), (1300, 0.15, 0.004)],
        },
        "up": {
            "dur": 0.016,
            "bursts": [(0.55, 0.0003, 2000, 15000)],
            "body": [(3100, 0.15, 0.002)],
        },
    },
    # heavy and deep, a big button
    "mouse-heavy": {
        "gain": 0.85,
        "down": {
            "dur": 0.055,
            "bursts": [(0.70, 0.0010, 300, 7000)],
            "body": [(320, 0.60, 0.012), (160, 0.40, 0.018)],
        },
        "up": {
            "dur": 0.035,
            "bursts": [(0.45, 0.0007, 400, 8000)],
            "body": [(420, 0.30, 0.008)],
        },
    },
    # hollow plastic, the ball mouse of the 90s
    "mouse-retro": {
        "gain": 0.82,
        "down": {
            "dur": 0.045,
            "bursts": [(0.75, 0.0007, 600, 10000)],
            "body": [(950, 0.45, 0.010), (1900, 0.20, 0.006), (430, 0.30, 0.014)],
        },
        "up": {
            "dur": 0.030,
            "bursts": [(0.50, 0.0005, 800, 11000)],
            "body": [(1200, 0.25, 0.006)],
        },
    },
    # two stages very close together: the travel then the click
    "mouse-gaming": {
        "gain": 0.78,
        "down": {
            "dur": 0.020,
            "bursts": [(0.55, 0.0003, 1600, 14000), (0.80, 0.0004, 1200, 12000, 0.0025)],
            "body": [(3400, 0.22, 0.002), (1800, 0.18, 0.003)],
        },
        "up": {
            "dur": 0.014,
            "bursts": [(0.50, 0.0003, 1600, 14000)],
            "body": [(4000, 0.14, 0.0015)],
        },
    },
    # a tiny tick, barely audible
    "mouse-tick": {
        "gain": 0.50,
        "down": {
            "dur": 0.018,
            "bursts": [(0.45, 0.0003, 2500, 16000)],
            "body": [(5200, 0.12, 0.0015)],
        },
        "up": {
            "dur": 0.012,
            "bursts": [(0.30, 0.0002, 3000, 16000)],
            "body": [(6000, 0.08, 0.0010)],
        },
    },
    # clacky, you hear it from across the room
    "mouse-clacky": {
        "gain": 0.90,
        "down": {
            "dur": 0.040,
            "bursts": [(0.90, 0.0006, 900, 12000), (0.45, 0.0004, 1500, 14000, 0.0022)],
            "body": [(1100, 0.35, 0.006), (480, 0.30, 0.010)],
        },
        "up": {
            "dur": 0.026,
            "bursts": [(0.55, 0.0004, 1200, 13000)],
            "body": [(1600, 0.20, 0.004)],
        },
    },
    # thin shell ringing after the click
    "mouse-hollow": {
        "gain": 0.70,
        "down": {
            "dur": 0.060,
            "bursts": [(0.50, 0.0006, 500, 9000)],
            "body": [(820, 0.55, 0.018), (1640, 0.20, 0.010)],
        },
        "up": {
            "dur": 0.035,
            "bursts": [(0.30, 0.0004, 700, 9500)],
            "body": [(1050, 0.30, 0.010)],
        },
    },
    # dull and matte, the click of a trackpad
    "mouse-trackpad": {
        "gain": 0.65,
        "down": {
            "dur": 0.035,
            "bursts": [(0.35, 0.0009, 80, 1500)],
            "body": [(180, 0.70, 0.012), (90, 0.40, 0.016)],
        },
        "up": {
            "dur": 0.025,
            "bursts": [(0.22, 0.0007, 100, 1800)],
            "body": [(220, 0.35, 0.009)],
        },
    },
}


def build():
    for pack, cfg in PACKS.items():
        rendered = {}
        peak = 0.0
        for kind, spec in cfg.items():
            if kind == "gain":
                continue
            for v in range(VARIANTS):
                # fixed seed: regenerating gives exactly the same files
                samples = render(spec, f"{pack}/{kind}/{v}")
                rendered[(kind, v)] = samples
                peak = max(peak, max(abs(s) for s in samples))
        # one reference level per pack: the release stays quieter than the
        # press, and "felt" stays softer than "clack"
        scale = (0.92 / peak) * cfg["gain"]
        for (kind, v), samples in rendered.items():
            write_wav(
                os.path.join(OUT, pack, f"{kind}-{v + 1}.wav"), [s * scale for s in samples]
            )
        print(f"{pack}: {len(rendered)} sounds")


def signature(vals):
    """Three measures that are enough to tell two sounds apart by ear:
    duration, brightness (zero crossings) and decay time."""
    peak = max(abs(s) for s in vals)
    head = vals[: int(0.020 * SR)]
    crossings = sum(1 for a, b in zip(head, head[1:]) if (a >= 0) != (b >= 0))
    tail = max(i for i, s in enumerate(vals) if abs(s) > 0.1 * peak)
    return (len(vals) / SR, crossings / (len(head) / SR), (tail + 1) / SR)


def check():
    """Checks that what was written is playable and is not silence."""
    total = 0
    sigs = {}
    for pack, cfg in PACKS.items():
        kinds = [k for k in cfg if k != "gain"]
        for kind in kinds:
            seen = []
            for v in range(1, VARIANTS + 1):
                path = os.path.join(OUT, pack, f"{kind}-{v}.wav")
                assert os.path.exists(path), f"missing: {path}"
                with wave.open(path, "rb") as w:
                    assert w.getframerate() == SR, path
                    assert w.getnchannels() == 1, path
                    assert w.getsampwidth() == 2, path
                    raw = w.readframes(w.getnframes())
                vals = struct.unpack(f"<{len(raw) // 2}h", raw)
                peak = max(abs(s) for s in vals) / 32768.0
                assert 0.02 < peak <= 1.0, f"{path}: level {peak:.3f} out of range"
                dur = len(vals) / SR
                assert 0.010 < dur < 0.30, f"{path}: duration {dur:.3f}s out of range"
                assert raw not in seen, f"{path}: variant identical to another"
                seen.append(raw)
                if kind == "down" and v == 1:
                    sigs[pack] = signature(vals)
                total += 1

    # The point of the set is to offer different sounds: two packs of the same
    # family must differ by at least 15% on one of the three measures.
    for family in (False, True):
        names = [p for p in sigs if p.startswith("mouse") is family]
        for a, b in itertools.combinations(names, 2):
            spread = max(abs(x - y) / max(x, y) for x, y in zip(sigs[a], sigs[b]))
            assert spread > 0.15, f"{a} and {b} sound the same (spread {spread:.0%})"

    print(f"OK: {total} valid files, {len(sigs)} distinct packs")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        build()
        check()
