#!/usr/bin/env python3
"""Fabrique les sons de Clack (WAV 48 kHz mono 16 bits).

Aucune dependance : uniquement la bibliotheque standard.
Les sons sont synthetises, donc libres de droits et modifiables ici meme.

Recette d'un clic : une bouffee de bruit tres courte (le contact plastique)
posee sur des sinusoides amorties (la resonance du boitier).

    python3 tools/make_sounds.py          # genere Sounds/
    python3 tools/make_sounds.py --check  # verifie ce qui a ete genere
"""

import math
import os
import random
import struct
import sys
import wave

SR = 48000
VARIANTS = 3  # trois versions de chaque son, tirees au hasard a la frappe
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Sounds")

# --- briques de synthese -----------------------------------------------------


def lowpass(x, fc):
    """Filtre passe-bas 1 pole : coupe les aigus au-dessus de fc."""
    a = 1.0 - math.exp(-2.0 * math.pi * fc / SR)
    y = 0.0
    out = []
    for v in x:
        y += a * (v - y)
        out.append(y)
    return out


def highpass(x, fc):
    """Passe-haut 1 pole : le signal moins ses graves."""
    lp = lowpass(x, fc)
    return [v - l for v, l in zip(x, lp)]


def burst(buf, rng, amp, tau, hp, lp, offset=0.0):
    """Bouffee de bruit filtree, en decroissance exponentielle."""
    n = min(int(tau * 12 * SR) + 8, len(buf))
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    noise = lowpass(highpass(noise, hp), lp)
    start = int(offset * SR)
    for i, v in enumerate(noise):
        j = start + i
        if j >= len(buf):
            break
        buf[j] += amp * v * math.exp(-i / (tau * SR))


def body(buf, freq, amp, tau):
    """Sinusoide amortie : la resonance du boitier ou de la touche."""
    n = min(int(tau * 9 * SR) + 8, len(buf))
    w = 2.0 * math.pi * freq / SR
    for i in range(n):
        buf[i] += amp * math.exp(-i / (tau * SR)) * math.sin(w * i)


def render(spec, seed):
    rng = random.Random(seed)
    buf = [0.0] * int(spec["dur"] * SR)
    for b in spec["bursts"]:
        burst(buf, rng, *b)
    # chaque variante desaccorde legerement la resonance : evite l'effet robot
    for freq, amp, tau in spec["body"]:
        body(buf, freq * rng.uniform(0.96, 1.04), amp * rng.uniform(0.92, 1.06), tau)
    fade(buf)
    return buf


def fade(buf):
    """Rampes tres courtes aux deux bouts pour ne pas claquer."""
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


# --- les ambiances -----------------------------------------------------------
# bursts : (amplitude, duree de decroissance, coupe-bas, coupe-haut, decalage)
# body   : (frequence, amplitude, duree de decroissance)

PACKS = {
    # profond et amorti, facon clavier moderne rempli de mousse
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
    # sec et brillant, facon switch a clic
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
    # discret, utilisable en open space
    "feutre": {
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
    # metallique et resonant, facon machine a ecrire
    "machine": {
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
    # le clic de souris : tres court et sec
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
}


def build():
    for pack, cfg in PACKS.items():
        rendered = {}
        peak = 0.0
        for kind, spec in cfg.items():
            if kind == "gain":
                continue
            for v in range(VARIANTS):
                # graine fixe : regenerer donne exactement les memes fichiers
                samples = render(spec, f"{pack}/{kind}/{v}")
                rendered[(kind, v)] = samples
                peak = max(peak, max(abs(s) for s in samples))
        # un seul volume de reference par ambiance : la relache reste plus
        # discrete que la frappe, et "feutre" reste plus doux que "clack"
        scale = (0.92 / peak) * cfg["gain"]
        for (kind, v), samples in rendered.items():
            write_wav(
                os.path.join(OUT, pack, f"{kind}-{v + 1}.wav"), [s * scale for s in samples]
            )
        print(f"{pack}: {len(rendered)} sons")


def check():
    """Verifie que ce qui a ete ecrit est jouable et n'est pas du silence."""
    total = 0
    for pack, cfg in PACKS.items():
        kinds = [k for k in cfg if k != "gain"]
        for kind in kinds:
            seen = []
            for v in range(1, VARIANTS + 1):
                path = os.path.join(OUT, pack, f"{kind}-{v}.wav")
                assert os.path.exists(path), f"manquant : {path}"
                with wave.open(path, "rb") as w:
                    assert w.getframerate() == SR, path
                    assert w.getnchannels() == 1, path
                    assert w.getsampwidth() == 2, path
                    raw = w.readframes(w.getnframes())
                vals = struct.unpack(f"<{len(raw) // 2}h", raw)
                peak = max(abs(s) for s in vals) / 32768.0
                assert 0.02 < peak <= 1.0, f"{path} : niveau {peak:.3f} hors limites"
                dur = len(vals) / SR
                assert 0.015 < dur < 0.25, f"{path} : duree {dur:.3f}s hors limites"
                assert raw not in seen, f"{path} : variante identique a une autre"
                seen.append(raw)
                total += 1
    print(f"OK : {total} fichiers valides")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        build()
        check()
