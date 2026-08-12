#!/bin/bash
# Construit Clack.app et l'installe dans /Applications, puis le lance.
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

# ponytail: signature locale ad hoc, faute de certificat Apple sur ce Mac.
# Consequence : chaque reconstruction change l'identite de l'app aux yeux de
# macOS, donc l'autorisation "Surveillance de la saisie" est a redonner.
# Pour y couper, il faudrait un certificat Developer ID.
codesign --force --sign - "$BUILD"

pkill -x Clack 2>/dev/null || true
sleep 1

# L'app reconstruite n'est plus la meme aux yeux de macOS : sans ce nettoyage,
# l'ancienne autorisation reste cochee dans les Reglages mais ne marche plus,
# et l'app est muette sans rien dire. On repart d'une demande neuve.
tccutil reset ListenEvent com.anthonywitz.clack >/dev/null 2>&1 || true
if [ -d "$APP" ]; then
	trash "$APP" 2>/dev/null || rm -rf "$APP"
fi
cp -R "$BUILD" "$APP"
open "$APP"
echo "Clack installe dans $APP et lance."
