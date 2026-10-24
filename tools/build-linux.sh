#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
rom="$repo/monsterparty.nes"
build="$repo/build-linux"
python=python3
jobs=4
version=0.1.2
cmake_args=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --rom) rom="$2"; shift 2 ;;
        --build) build="$2"; shift 2 ;;
        --python) python="$2"; shift 2 ;;
        --jobs) jobs="$2"; shift 2 ;;
        --version) version="$2"; shift 2 ;;
        --sdl2-prefix) cmake_args+=("-DCMAKE_PREFIX_PATH=$2" "-DSDL2_DIR=$2/lib/cmake/SDL2"); shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
mkdir -p "$build"
export TMPDIR="${TMPDIR:-$build/tmp}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$build/.cache}"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME"
cmake -S "$repo" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DNESRECOMP_BACKEND=cycle -DNESRECOMP_ENABLE_TRACE=OFF \
    -DNESRECOMP_ENABLE_NET=OFF -DNESRECOMP_GAME_VERSION="$version" \
    -DNESRECOMP_ROM="$rom" -DPython3_EXECUTABLE="$(command -v "$python")" "${cmake_args[@]}"
cmake --build "$build" --parallel "$jobs"
