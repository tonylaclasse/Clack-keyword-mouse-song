# Clack

The sound of a mechanical keyboard and of a mouse click, from the Mac menu bar.

## Install

macOS 13 or later, on Intel Macs as well as Apple Silicon. You need Apple's
developer tools, free, once and for all:

```
xcode-select --install
```

Then, in the project folder:

```
./build.sh
```

The script builds the app, copies it into `/Applications` and launches it. It
has no Dock icon and no window: everything happens from the keyboard icon in the
top right. If a version was already installed, it is replaced.

Building the app yourself avoids the macOS block on apps downloaded without an
Apple certificate.

## The permission, once

macOS forbids any app from hearing the keyboard until you allow it.

1. System Settings, Privacy & Security, **Input Monitoring**
2. Tick **Clack**

Until that is done, the menu shows "Allow in System Settings". Once ticked, the
sound starts within two seconds, without relaunching the app.

In a password field, macOS cuts off keyboard access: total silence. That is the
system doing its job.

This is the same permission spyware asks for, so let's be clear: Clack keeps
nothing, writes nothing to disk and connects to no network. It asks the system
for permission to listen only, never to modify a keystroke. All of it fits in one
417-line file, `Sources/main.swift`, readable in ten minutes.

## The menu

- **Sounds enabled**: mutes everything in one click
- **Keyboard**: ten packs — Thock (deep), Clack (clacky), Felt (quiet),
  Typewriter, Cream (soft and round), Marble (bright and crisp), Spring (IBM
  Model M), Laptop (flat and thin), Wood (warm and hollow), Bubble (all pop)
- **Mouse click**: ten clicks to choose from — classic, soft, sharp, heavy,
  retro, gaming, tick, clacky, hollow, trackpad — or *None* to hear the keyboard
  only
- **Volume**
- **Open at login**

Every sound comes in three variants picked at random, with a slightly different
volume on each keystroke: no two keys ever sound exactly the same. The space bar
has its own, deeper sound, like on a real keyboard.

## Changing the sounds

The sounds are built by `tools/make_sounds.py` (no dependencies). Edit the
recipes at the top of the file, then:

```
python3 tools/make_sounds.py && ./build.sh
```

To try things out without rebuilding the app, drop your own files into
`~/Library/Application Support/Clack/Sounds/`, keeping the same layout
(`thock/down-1.wav`, `up-1.wav`, `space-1.wav`, and so on). The app picks those
first, and then replaces *every* sound: that folder must contain the packs you
want, complete. A folder whose name starts with `mouse` is offered as a mouse
click and does not need `space-*.wav`.

## Rebuilding

Every `./build.sh` changes the identity of the app in the eyes of macOS, so the
permission has to be granted again. The script deletes the old one so that a new
request appears instead of a ticked box that no longer works. An Apple Developer
ID certificate would remove this step.
