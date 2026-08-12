#!/usr/bin/env python3
"""Fabrique les sons de Clack (WAV 48 kHz mono 16 bits).

Aucune dependance : uniquement la bibliotheque standard.
Les sons sont synthetises, donc libres de droits et modifiables ici meme.

Recette d'un clic : une bouffee de bruit tres courte (le contact plastique)
posee sur des sinusoides amorties (la resonance du boitier).

    python3 tools/make_sounds.py          # genere Sounds/
    python3 tools/make_sounds.py --check  # verifie ce qui a ete genere
"""

import itertools
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


def body(buf, freq, amp, tau, offset=0.0):
    """Sinusoide amortie : la resonance du boitier ou de la touche.

    Le decalage sert aux sons en deux temps, tel le ressort qui claque puis
    chante une fraction de milliseconde plus tard.
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
    # chaque variante desaccorde legerement la resonance : evite l'effet robot
    for freq, amp, tau, *rest in spec["body"]:
        body(buf, freq * rng.uniform(0.96, 1.04), amp * rng.uniform(0.92, 1.06), tau,
             rest[0] if rest else 0.0)
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
# body   : (frequence, amplitude, duree de decroissance, decalage)
# Un pack dont le nom commence par "mouse" est un clic de souris : pas de barre
# d'espace, et l'app le propose dans un menu separe.

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
    # rond et doux, facon switch lineaire lubrifie
    "creme": {
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
    # aigu et net, le "poc" d'un clavier a plaque rigide
    "marbre": {
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
    # le claquement puis le chant du ressort, facon IBM Model M
    "ressort": {
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
    # plat et fin, le clavier d'un portable
    "portable": {
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
    # chaud et creux, une caisse en bois
    "bois": {
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
    # presque pas de bruit de contact : une bulle qui eclate
    "bulle": {
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
    # --- les clics de souris : tres courts, sans barre d'espace ---------------
    # le clic classique
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
    # feutre, pour travailler a cote de quelqu'un
    "mouse-doux": {
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
    # sec et aigu, presque un declic de stylo
    "mouse-sec": {
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
    # lourd et profond, un gros bouton
    "mouse-lourd": {
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
    # plastique creux, la souris a boule des annees 90
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
    # deux temps tres rapproches : la course puis le declic
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
    # un tic minuscule, a peine audible
    "mouse-tic": {
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
    # claquant, on l'entend d'un bout a l'autre de la piece
    "mouse-clac": {
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
    # coque fine qui resonne apres le clic
    "mouse-creux": {
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
    # sourd et mat, le clic d'un trackpad
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


def signature(vals):
    """Trois mesures qui suffisent a separer deux sons a l'oreille : duree,
    brillance (passages par zero) et temps de decroissance."""
    peak = max(abs(s) for s in vals)
    head = vals[: int(0.020 * SR)]
    crossings = sum(1 for a, b in zip(head, head[1:]) if (a >= 0) != (b >= 0))
    tail = max(i for i, s in enumerate(vals) if abs(s) > 0.1 * peak)
    return (len(vals) / SR, crossings / (len(head) / SR), (tail + 1) / SR)


def check():
    """Verifie que ce qui a ete ecrit est jouable et n'est pas du silence."""
    total = 0
    sigs = {}
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
                assert 0.010 < dur < 0.30, f"{path} : duree {dur:.3f}s hors limites"
                assert raw not in seen, f"{path} : variante identique a une autre"
                seen.append(raw)
                if kind == "down" and v == 1:
                    sigs[pack] = signature(vals)
                total += 1

    # Le but du lot est d'offrir des sons differents : deux packs de la meme
    # famille doivent s'ecarter d'au moins 15 % sur une des trois mesures.
    for family in (False, True):
        names = [p for p in sigs if p.startswith("mouse") is family]
        for a, b in itertools.combinations(names, 2):
            spread = max(abs(x - y) / max(x, y) for x, y in zip(sigs[a], sigs[b]))
            assert spread > 0.15, f"{a} et {b} sonnent pareil (ecart {spread:.0%})"

    print(f"OK : {total} fichiers valides, {len(sigs)} packs distincts")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        build()
        check()
