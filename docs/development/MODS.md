# Cheats and Prototype Restoration

The two optional packages start disabled. Widescreen keeps its existing single
Aspect setting, viewport activation, stage-edge camera, centered HUD and centered
guardian rooms.

## Credits and patch identity

Prototype Restoration 1.0 is by **Cubivore10**:

- Original listing: https://www.romhacking.net/hacks/1516/
- Current archive: https://www.romhack.ing/hacks/1516/
- Original IPS SHA-256: `c5eac2f185abeefd585235516a5dadc4ef2c271794dd4bdb6906bc82d04e52d8`
- USA input payload CRC32: `02B9E7C2`; restored payload: `71DB905B`.

The supplied archive contains the original IPS only. CMake checks its SHA-256
before embedding it. No complete or patched ROM is distributed. The game checks
input/output CRCs, applies the original IPS in memory, and leaves the owner's ROM
file unchanged. The IPS repeats nine zero reserved header bytes; that record
has no payload effect. Geometry stays 128 KiB PRG + 128 KiB CHR.

Of 3,375 changed bytes, 215 are PRG data in 16 KiB banks 2, 3 and 6; 3,160 are
CHR graphics. None overlaps the generated union of compiled instruction bytes,
including operands and alternate bank/slot mappings. The engine refuses a data
overlay touching that union before changing either PRG or CHR. Accepted data
changes keep native dispatch and refresh folded ROM reads from the mapped image.
The ordinary writable-PRG API still disables native execution.

Restoration is locked for the running session. Its setting remains available
in the next launcher's Mods page. Widescreen invalidates PRG/CHR caches after
boot-time content changes. The changed PRG hash distinguishes stock/restored
snapshots.

## Cheat implementation

Sources: https://gamehacking.org/game/30365 and
https://gamegenie.com/cheats/gamegenie/nes/monster_party.html.
Galoob, Ugetab and megaman_exe are credited in the package notice and launcher.

| Feature | Implementation |
| --- | --- |
| Invincibility | Content-keyed hook at `4:879A`, matching the early return of Ugetab's `AVOEZYSZ`. |
| One-hit regular enemies | `5:8502`: reduce the hit target's nonzero HP to 1 before the game's normal damage/defeat path. |
| One-hit guardians | `5:8D22`: same landed-hit approach as the validated coverage assist, without developer logging. |
| Endless Bert | `4:804A`: keep the timer at zero while transformed; a real pill is still needed. |
| Energy | Bank 4 read substitutions at `9532/94C6`, values 12/24/44. |
| Round | Bank 4 `954A` immediate, values 0–7; applies when starting a new game. |
| Walking speed | Bank 4 `82B8/82CE`, signed movement 1/2/4. |
| Jump height | Bank 4 `8555–8557`, the documented high/extra-high tables. |

Read substitutions match physical PRG offsets and original values, including
folded native reads. They can be registered before ROM loading for the launcher.
Opcode changes are represented by hooks, rather than editing instructions that
have already become C. Reset callbacks restore stock policy when disabled.
The game never writes guardian defeat flags or gives the round key directly.

Cheat policy is checked when loading snapshots; use the same cheat settings.
Changing mods clears rewind through the shared host. Policy has no guest-time
counters. Both cheats and restoration request local play, and the shared online
launch path uses the stock mod plan.

## Reproducing validation

Use the native Windows Python with `-I -B`, or Python 3.11+ on Linux. Every
automation run is silent and uses isolated catalogs and output directories.

- `tests/mods/validate.py --exe EXE --out OUT`: every setting, all eight starting
  rounds, disabled equality, native/interpreter hashes/pictures/states, measured
  speed/jump height, restored title and combined save/load replay.
- A build with `MONSTERPARTY_MOD_TESTS=ON`, plus `--require-probes`, also exercises
  the original damage, landed-hit and Bert-expiry routines in restored isolated
  machine snapshots. Release packaging refuses that developer build.
- `tests/mods/campaign.py --exe EXE --out OUT`: restoration, invincibility and
  guardian one-hit assistance through all table-derived doors, guardian defeat
  paths, round exits and the ending. Patched content tables are decoded in
  memory. Position/life fixtures are setup assistance, never victory evidence.
- `tests/state_ui.py --exe EXE --out OUT --mods-root CATALOG --fixture STATE`:
  the real F7/F8 keyboard/controller interfaces, exact snapshots, invalid loads,
  rewind cancellation/commit and saves surviving a process restart.
- `tests/mods/bert.py`: an actual pill pickup followed by 3,600 frames of flight
  beyond normal expiry, with native/interpreter replay. The prerequisite item
  fixture does not write the transformation flag or timer.
- `tests/mods/inspect_campaign.py`: inspect every completed campaign capture
  for centered HUD pixels and the native inner image of each room.
- Engine `cyc_data_mods`: ROM-free opcode/operand protection, atomic rejection,
  folded reads, bank/compare isolation, pre-ROM registration and scope refusal.
- Engine mod-runtime tests: boot locks, exclusion preflight, option locks,
  relaunch reset, HD-pack and external-ROM gate regressions.

Current-build snapshots matter; compatibility with older builds is not required.

## 0.1.2 results

Windows and Ubuntu-baseline Linux builds passed all 27 setting/replay cases.
Native/interpreter hashes, native/presented pixels and complete states matched.
The cross-platform audit matched 224 comparisons across 56 retained runs (hashes
compared at common frame numbers). Measured eight-frame walking distances were
8/16/32 pixels; jump Y minima were 116/88/72 for normal/high/extra-high.

The restoration campaign visited all 132 table-derived doors in rounds 1–8,
defeated the guardians through landed hits, traversed real exits and reached the
final guardian and credits. It used position/life setup assistance plus the
player's guardian one-hit and invincibility mods. The projectile-boss route
holds position and jumps to reflect shots; with invincibility, knockback no
longer keeps a walking route in place. Door checks wait for Bert's original
expiry when UP is being used for flight. No victory or transformation flag is
forced. Pixel inspection passed 349 captures, including 161 room captures.

The real Windows/Linux F7/F8 suites passed with restoration, cheats and 32:9
combined. The Linux AppImage also passed save/load, rewind, state persistence,
payload refresh preserving player data, and rewind-off retaining the browser.
The original/restored title screens were reviewed, as were the final credits.
