# Release checklist

1. Update the project/build versions and player instructions together.
2. Build the Windows launcher with `tools/build.ps1`, then package with
   `tools/package.ps1`. Keep the complete dependency set in the ZIP.
3. Build Linux on the supported baseline and package with `tools/package-linux.sh`.
   Use verified linuxdeploy/appimagetool binaries and upstream runtime notices.
   Keep system graphics drivers and the C++ runtime outside the bundle.
4. Run the round matrix and real catalog checks from `tests/widescreen/validate.py`.
   Check Windows launcher screens with `tests/launcher.py` in an isolated runtime.
   Use `tests/linux_release.py` for AppImage gameplay comparisons, and
   `tests/linux_launcher.py` under Xvfb for picker and user-data checks.
5. Inspect actual gameplay screenshots and both packaged launchers. Verify
   windowed defaults, normal owner-facing audio, and Aspect as the only
   widescreen option.
6. Audit source history and final assets for ROMs, personal files and credentials.
   Do not ship diagnostic captures, test software renderers, or loading-speed mods.
   Generate `SHA256SUMS.txt` for both platform assets.
7. Commit finished work, tag the version, and publish the two assets plus checksums.
   Verify the public tag, release links and downloaded asset hashes.

Linux settings and game files live under `$XDG_DATA_HOME/MonsterParty`, defaulting
to `~/.local/share/MonsterParty`. The AppImage refreshes only its owned runtime
files and leaves user settings, saves and additional mods in place.

Clean disposable staging, extraction and test runtime directories after release.
Preserve required evidence and owner playtest profiles, and record retained
temporary data and its cleanup needs in the issue tracker.
