# Building Monster Party

Clone with submodules and supply your original Monster Party (USA) ROM:

```sh
git clone --recursive https://github.com/mstan/MonsterPartyNESRecomp.git
cd MonsterPartyNESRecomp
```

Place `monsterparty.nes` in the repository root, or pass its location to the
build script. The build checks that it matches the supported USA release.
ROMs and generated game data must stay out of source control and release assets.

## Windows

Install Visual Studio 2022 Community with the C++ workload and Python 3.12.
The script uses Visual Studio's bundled CMake and Ninja.

```powershell
.\tools\build.ps1 -BuildDir build-release
.\tools\package.ps1 -BuildDir build-release -SkipBuild
```

Pass `-Rom` to use a ROM elsewhere. `-Trace` enables development tracing.
The release packager requires a build with tracing disabled and launcher enabled.

## Linux

Install a C/C++ toolchain, CMake, Ninja, Python 3.11 or newer, SDL2 2.24 or newer,
and OpenGL development libraries. For example, on Ubuntu 24.04:

```sh
sudo apt install build-essential cmake ninja-build python3 libsdl2-dev libgl-dev
bash tools/build-linux.sh --build build-linux
```

Use `--rom`, `--python`, `--jobs` and `--sdl2-prefix` to select local dependencies.
The published x86-64 AppImage is built on Ubuntu 22.04 with SDL2 2.30.12, then
tested on Ubuntu 24.04. `tools/package-linux.sh` packages an existing build using
linuxdeploy, appimagetool and patchelf. Supply its build, fresh work directory,
output filename, tool paths, Python interpreter and runtime-notices directory.
It bundles SDL2 and uses the host graphics and C++ runtimes. It does not include
a ROM.

## Working on the game

Game integrations live in `src/`, the widescreen package in `mods/`, and
reproducible checks in `tests/`. The engine and launcher are pinned submodules;
update their pins deliberately.

See [validation](development/VALIDATION.md) for content coverage and known
limitations, and [widescreen development](development/WIDESCREEN.md) for rendering
and camera details. Automated runs use hidden or headless windows and muted
output. Keep temporary build/capture data bounded and clean it up after use.
