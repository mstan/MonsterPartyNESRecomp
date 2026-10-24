#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
build="${1:?Usage: package-linux.sh BUILD WORK OUTPUT LINUXDEPLOY APPIMAGETOOL [PYTHON]}"
work="${2:?Missing work directory}"
output="${3:?Missing output AppImage}"
linuxdeploy="${4:?Missing linuxdeploy AppImage}"
appimagetool="${5:?Missing appimagetool AppImage}"
python="${6:-python3}"
runtime_notices="${7:?Missing AppImage runtime notices directory}"
appdir="$work/MonsterParty.AppDir"
if [ -e "$appdir" ] || [ -e "$output" ]; then
    echo 'Choose a fresh staging directory and output filename.' >&2
    exit 2
fi
mkdir -p "$appdir/usr/bin" "$work/tmp" "$(dirname "$output")"
export TMPDIR="$work/tmp"
export APPIMAGE_EXTRACT_AND_RUN=1
export PYTHONDONTWRITEBYTECODE=1
version="$(sed -nE 's/^NESRECOMP_GAME_VERSION:[^=]+=//p' "$build/CMakeCache.txt")"
[ -n "$version" ] || { echo 'Build has no release version' >&2; exit 2; }
grep -q '^MONSTERPARTY_MOD_TESTS:BOOL=OFF$' "$build/CMakeCache.txt" || {
    echo 'Developer mod probes must be disabled in release builds' >&2; exit 2;
}
"$python" "$repo/tools/stage_release.py" --build "$build" --output "$appdir/usr/bin" --version "$version"
cp "$build/MonsterPartyRecomp" "$appdir/usr/bin/"
strip "$appdir/usr/bin/MonsterPartyRecomp"
cat > "$work/monster-party.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Monster Party
Exec=MonsterPartyRecomp
Icon=monster-party
Categories=Game;
Terminal=false
EOF
cp "$repo/assets/icon.png" "$work/monster-party.png"
"$linuxdeploy" --appimage-extract-and-run --appdir "$appdir" \
    --executable "$appdir/usr/bin/MonsterPartyRecomp" \
    --desktop-file "$work/monster-party.desktop" --icon-file "$work/monster-party.png"
# Use the host C++ runtime. An older bundled libstdc++ can prevent newer Mesa
# drivers from loading in this same process. Ubuntu 22.04 is the release baseline.
patchelf --set-rpath '$ORIGIN/lib:$ORIGIN/../lib' "$appdir/usr/bin/MonsterPartyRecomp"
env -u LD_LIBRARY_PATH ldd "$appdir/usr/bin/MonsterPartyRecomp" \
    | awk '{for(i=1;i<=NF;i++) if($i ~ /^\//) print $i}' \
    | while read -r p; do readlink -f "$p"; done | sort -u > "$work/keep-libraries.txt"
for file in "$appdir"/usr/lib/*; do
    [ -f "$file" ] || continue
    if ! grep -qxF "$(readlink -f "$file")" "$work/keep-libraries.txt"; then rm -- "$file"; fi
done
if env -u LD_LIBRARY_PATH ldd "$appdir/usr/bin/MonsterPartyRecomp" | grep -q 'not found'; then
    echo 'Unresolved packaged dependency' >&2
    exit 1
fi
# Include distro copyright notices for the exact shared objects in the bundle.
mkdir -p "$appdir/usr/bin/licenses/linux"
for file in "$appdir"/usr/lib/*; do
    [ -f "$file" ] || continue
    soname="$(basename "$file")"
    source="$(ldd "$build/MonsterPartyRecomp" | awk -v lib="$soname" '$1 == lib {print $3; exit}')"
    [ -n "$source" ] || continue
    package="$(dpkg-query -S "$(readlink -f "$source")" 2>/dev/null | head -1 | sed 's/: \/.*//' || true)"
    [ -n "$package" ] || continue
    notice="/usr/share/doc/${package%%:*}/copyright"
    [ ! -f "$notice" ] || cp "$notice" "$appdir/usr/bin/licenses/linux/${package//:/-}.txt"
done
# SDL2 is built locally, so it has no dpkg ownership record.
sdl2_dir="$(sed -nE 's/^SDL2_DIR:[^=]+=//p' "$build/CMakeCache.txt")"
sdl2_notice="${SDL2_LICENSE:-${sdl2_dir%/lib/cmake/SDL2}/share/licenses/SDL2/LICENSE.txt}"
if [ -f "$sdl2_notice" ]; then
    cp "$sdl2_notice" "$appdir/usr/bin/licenses/SDL2-COPYING.txt"
fi
cp "$runtime_notices"/*.txt "$appdir/usr/bin/licenses/linux/"
rm -f "$appdir/AppRun"
cp "$repo/tools/AppRun" "$appdir/AppRun"
chmod +x "$appdir/AppRun"
"$python" "$repo/tools/release_payload.py" "$appdir"
# Reuse the verified tool's own runtime instead of fetching an unpinned one.
offset="$("$appimagetool" --appimage-offset)"
head -c "$offset" "$appimagetool" > "$work/runtime-x86_64"
ARCH=x86_64 "$appimagetool" --appimage-extract-and-run --runtime-file "$work/runtime-x86_64" "$appdir" "$output"
chmod +x "$output"
sha256sum "$output"
