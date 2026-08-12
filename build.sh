#!/bin/bash
# Builds Clack.app, installs it into /Applications, then launches it.
set -euo pipefail
cd "$(dirname "$0")"

BUILD="build/Clack.app"
APP="/Applications/Clack.app"

[ -d Sounds ] || python3 tools/make_sounds.py

rm -rf build
mkdir -p "$BUILD/Contents/MacOS" "$BUILD/Contents/Resources"

swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos13.0" \
	Sources/main.swift -o "$BUILD/Contents/MacOS/Clack"

cp Sources/Info.plist "$BUILD/Contents/Info.plist"
cp -R Sounds "$BUILD/Contents/Resources/Sounds"

# ponytail: ad hoc local signature, for lack of an Apple certificate on this Mac.
# Consequence: every rebuild changes the identity of the app in the eyes of
# macOS, so the "Input Monitoring" permission has to be granted again.
# A Developer ID certificate would remove that step.
codesign --force --sign - "$BUILD"

pkill -x Clack 2>/dev/null || true
sleep 1

# The rebuilt app is no longer the same one in the eyes of macOS: without this
# cleanup the old permission stays ticked in Settings but no longer works, and
# the app is silent without saying a word. Start from a fresh request instead.
tccutil reset ListenEvent com.anthonywitz.clack >/dev/null 2>&1 || true
if [ -d "$APP" ]; then
	trash "$APP" 2>/dev/null || rm -rf "$APP"
fi
cp -R "$BUILD" "$APP"
open "$APP"
echo "Clack installed in $APP and launched."
