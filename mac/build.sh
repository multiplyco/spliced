#!/bin/sh
# Build Spliced.app (and a .dmg with --dmg) from this checkout: the Swift shell, the engine (../spliced, the same
# package `spliced` runs), the command that runs it, and uv.
#   mac/build.sh                  -> mac/build/Spliced.app, for this Mac's chip, signed ad hoc (runs on this Mac)
#   mac/build.sh --dmg            -> also mac/build/Spliced-<version>.dmg
#   mac/build.sh --universal      -> Apple silicon and Intel in one app, with uv for both (downloaded, same version)
# Signing for other Macs, when the environment has it (a release does this in CI, .github/workflows/release.yml):
#   SPLICED_SIGN_IDENTITY="Developer ID Application: <Company> (<TEAM>)"   signs with the hardened runtime
#   SPLICED_NOTARY_PROFILE=<profile>   notarises the dmg and staples it (a profile made once with
#                                      xcrun notarytool store-credentials <profile> --apple-id ... --team-id ...)
set -eu
cd "$(dirname "$0")"
MAC="$(pwd)"
REPO="$(cd .. && pwd)"
OUT="$MAC/build"
APP="$OUT/Spliced.app"
VERSION="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$REPO/spliced/__init__.py")"
BUILD="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo dev)"
DMG=0; UNIVERSAL=0
for a in "$@"; do case "$a" in --dmg) DMG=1 ;; --universal) UNIVERSAL=1 ;; *) echo "unknown option $a" >&2; exit 2 ;; esac; done

echo "Spliced $VERSION ($BUILD)"
if [ "$UNIVERSAL" = 1 ]; then
  swift build -c release --triple arm64-apple-macosx13.0
  swift build -c release --triple x86_64-apple-macosx13.0
  BIN="$OUT/Spliced.bin"; mkdir -p "$OUT"
  lipo -create .build/arm64-apple-macosx/release/Spliced .build/x86_64-apple-macosx/release/Spliced -output "$BIN"
else
  swift build -c release
  BIN="$(swift build -c release --show-bin-path)/Spliced"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/bin" "$APP/Contents/Resources/tools" "$APP/Contents/Resources/engine"
cp "$BIN" "$APP/Contents/MacOS/Spliced"
sed -e "s/__VERSION__/$VERSION/" -e "s/__BUILD__/$BUILD/" Resources/Info.plist > "$APP/Contents/Info.plist"
# a build for this Mac remembers the clone it came from, so a copy moved to Applications still updates from it
# (Updates.swift); a disk image is for other Macs, where this path means nothing
if [ "$DMG" = 0 ] && [ -e "$REPO/.git" ]; then /usr/libexec/PlistBuddy -c "Add :SplicedCheckout string $REPO" "$APP/Contents/Info.plist"; fi
cp Resources/AppIcon.icns "$APP/Contents/Resources/"
cp Resources/spliced "$APP/Contents/Resources/bin/spliced"
# the engine: the package as it is in this checkout, without caches
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' "$REPO/spliced" "$APP/Contents/Resources/engine/"
printf '%s\n' "$BUILD" > "$APP/Contents/Resources/engine/spliced/BUILD"
# the example films `spliced kit starter` adds (looked up beside the package)
rsync -a --exclude '__pycache__' --exclude '.DS_Store' "$REPO/starter" "$APP/Contents/Resources/engine/"
# uv (in tools/, which goes on the engine's PATH; bin/ holds only the spliced command, which must not): runs the
# engine's heavier tools and fetches a Python when the Mac has none. SPLICED_UV points at another binary.
UVDEST="$APP/Contents/Resources/tools/uv"
if [ "$UNIVERSAL" = 1 ] && [ -z "${SPLICED_UV:-}" ]; then
  UVV="${UV_VERSION:-$(uv --version 2>/dev/null | awk '{print $2}')}"
  [ -n "$UVV" ] || { echo "set UV_VERSION (no uv here to copy the version from)" >&2; exit 1; }
  T="$(mktemp -d)"
  for arch in aarch64 x86_64; do
    curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UVV/uv-$arch-apple-darwin.tar.gz" | tar -xz -C "$T"
    mv "$T/uv-$arch-apple-darwin/uv" "$T/uv-$arch"
  done
  lipo -create "$T/uv-aarch64" "$T/uv-x86_64" -output "$UVDEST"
  rm -rf "$T"
  echo "uv $UVV, both chips"
else
  UV="${SPLICED_UV:-$(command -v uv || true)}"
  if [ -n "$UV" ]; then cp "$UV" "$UVDEST"; else echo "warning: no uv found; the app will need one on the Mac" >&2; fi
fi
chmod +x "$UVDEST" 2>/dev/null || true

if [ -n "${SPLICED_SIGN_IDENTITY:-}" ]; then
  # inside out: the nested binary, then the app (which seals the engine, the command and the icon as resources)
  [ -f "$UVDEST" ] && codesign --force --options runtime --timestamp --sign "$SPLICED_SIGN_IDENTITY" "$UVDEST"
  codesign --force --options runtime --timestamp --sign "$SPLICED_SIGN_IDENTITY" "$APP"
  codesign --verify --strict --verbose=1 "$APP"
  echo "signed with $SPLICED_SIGN_IDENTITY"
else
  codesign --force --deep --sign - "$APP" >/dev/null
fi
echo "built $APP ($(du -sh "$APP" | cut -f1))"

if [ "$DMG" = 1 ]; then
  STAGE="$OUT/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
  DMGF="$OUT/Spliced-$VERSION.dmg"
  # hdiutil's own guess at the image's size runs out of room for the app's many small files ("No space left on device")
  MB=$(du -sm "$STAGE" | cut -f1); MB=$((MB * 13 / 10 + 40))
  hdiutil create -quiet -size "${MB}m" -fs HFS+ -volname "Spliced $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMGF"
  rm -rf "$STAGE"
  if [ -n "${SPLICED_SIGN_IDENTITY:-}" ]; then codesign --force --timestamp --sign "$SPLICED_SIGN_IDENTITY" "$DMGF"; fi
  if [ -n "${SPLICED_NOTARY_PROFILE:-}" ]; then
    xcrun notarytool submit "$DMGF" --keychain-profile "$SPLICED_NOTARY_PROFILE" --wait
    xcrun stapler staple "$DMGF"
    echo "notarised"
  fi
  echo "built $DMGF"
fi
