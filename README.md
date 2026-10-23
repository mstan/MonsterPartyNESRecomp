# Monster Party

Monster Party (USA) for Windows x64, running on NESRecomp's cycle backend with
the recomp-ui launcher. Supply your own original USA ROM; no ROM is distributed.
The supported image has MMC1, eight 16 KiB PRG banks, and payload CRC32 `02B9E7C2`.

Select the matching ROM in the launcher. Arrow keys control movement, Z is A,
X is B, Enter is START, and backslash is SELECT. Escape opens the menu; controls
can be remapped. F8/F9 save and load execution snapshots. Snapshots are disposable
and specific to a build. Keep the game's passwords for persistent progress.

Adaptive widescreen is an optional mod in the Display group. Fit follows the
window's aspect; 16:9, 21:9, and 32:9 are also available. Original enemy activation
is the default. See [WIDESCREEN.md](WIDESCREEN.md) for behavior and validation.

## Build

Use Visual Studio 2022 Community with the C++ workload, its bundled CMake/Ninja,
and Windows Python 3.12. The submodules are pinned to NESRecomp `a76140c` and
recomp-ui `7c635c6`. This repository is local only; do not add a remote or push
without the owner's instruction.

```powershell
$env:TEMP = 'G:\Temp\Codex\MonsterPartyNESRecomp\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
.\tools\build.ps1 -Trace -BuildDir G:\Temp\Codex\MonsterPartyNESRecomp\build-validation
```

Put `monsterparty.nes` beside this README or pass `-Rom`. Build products, original
game data, save states, diagnostics and Ghidra databases are ignored. Source and
tool text use LF line endings. Keep temporary files and runtime data off C:.

## Headless coverage

All agent validation uses hidden processes, SDL dummy video/audio, `--no-save`,
journaled work-RAM fixtures, and retained commands/routes/screenshots/states.
Developer assists are disabled unless explicitly requested. `life` refills life;
`guardians` weakens a guardian only after a real hit lands, leaving the original
defeat code to run. Fixtures never patch guest code.

```powershell
& 'C:\Users\Matthew\AppData\Local\Programs\Python\Python312\python.exe' -I tests\coverage\campaign.py --tag audit --clear --parity --exe G:\Temp\Codex\MonsterPartyNESRecomp\build-validation\MonsterPartyRecomp.exe --output G:\Temp\Codex\MonsterPartyNESRecomp\audit
```

`tools/mp_doors.py` decodes all 132 round door entries. `tools/mp_map.py` reads
the live feature grid. The campaign visits rooms, audits maze destinations
against the decoded tables, defeats guardians and checks actual next-round
initialization. Independent maze and optional-encounter branches are recorded.
`tests/coverage/cases.py` covers title/attract, death/continue, pill pickup, Bert
flight/expiry and pause. `tests/coverage/ending.py` continues a genuine final-boss
entry through the ending. `tests/coverage/replay.py` compares a retained run with
a rebuilt native executable and its interpreter, byte for byte.

Only observed instruction starts are added by `tools/harvest_seeds.py`.
The self-modifying sound trampoline in stack RAM remains interpreted. Instructions
that straddle a 4 KiB program-view boundary can also remain interpreted despite
being seeded. These are execution fallbacks, not missing game handlers.

The release packager in `tools/package.ps1` builds with trace disabled, includes
the UI/assets/dependency notices, and verifies that ROMs, player data, test logs
and development fixtures are absent. It creates a local ZIP and publishes nothing.

Box artwork is the original Bandai package scan from
[StrategyWiki](https://strategywiki.org/wiki/Monster_Party); see `assets/SOURCE.txt`.
