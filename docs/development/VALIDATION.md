# Monster Party (USA) validation

ROM payload CRC32 `02B9E7C2`; NESRecomp `a76140c`; recomp-ui `7c635c6`.
Automated validation runs were headless or explicitly hidden, with speaker
output muted. Fixtures and commands are retained. Owner-requested interactive
handoffs use normal visible windows and enabled audio.

## Content and transitions

| Round | Door entries checked | Required guardians | Exit result |
| --- | ---: | ---: | --- |
| 1 | 6 | 3 | Round 2 initialized |
| 2 | 9 | 3 | Round 3 initialized |
| 3 | 6 | 3 | Round 4 initialized |
| 4 | 7 | 3 | Round 5 initialized |
| 5 | 6 | 2 | Round 6 initialized |
| 6 | 56 | 1 | Round 7 initialized |
| 7 | 36 | 2 | Round 8 initialized |
| 8 | 6 | 3 | Final boss entered |

All 132 door-table entries passed. Room and guardian entries use the original
area loader. Same-area maze destinations are checked against decoded destination
and arrival registers; camera position alone is insufficient because a hit can
move it after arrival. Room exits use the game's saved return point and real
walking. Round exits require naturally defeated guardians and real UP input;
no success flags or guardian counters are forced.

All required guardians, the optional third round-7 guardian, and the final boss
were defeated through original game code. The assist weakens a guardian only
after an actual hit lands. The round-4 projectile boss is defeated with real bat
input from a journaled position; reflected-shot trajectories were not separately
traced.
The final sequence was visually reviewed through the story, GRAPHICS credits,
and PRESENTED BY BANDAI / SHINSEI screen.

The original game allows the optional third round-7 defeat to underflow its
two-guardian count from 00 to FF. That encounter is retained as a separate audit
branch. The round exit uses the earlier checkpoint with two actual victories;
the counter is never repaired by a fixture.

Separate cases pass death/game-over and continue with life refill disabled,
picking up an assisted pill drop to become Bert, flight, timed return to Mark,
and pause freeze/resume. The pill fixture changes an enemy drop, not Mark's Bert
flag or transformation timer. Title/idle animation is retained as well.

These are assisted content/transition checks. Terrain/collision and enemy
interactions are sampled by recorded movement/combat routes; they are not an
exhaustive test of every collision tile or enemy behavior. Death/continue is
qualified in round 1. Every round's walk route has matching, non-silent emulated
WAV output between native and interpreter, with no sound sent to speakers.

## Native coverage and determinism

The 385 selected segments cover the eight complete round audits, extra cases,
final boss and ending. All native/interpreter frame hashes, native PNGs and
complete states match. Replaying the exact retained inputs on the builds before
and after seed generation also matches byte for byte.

| Metric | Before added seeds | After added seeds |
| --- | ---: | ---: |
| Interpreted ROM cycles | 12,977,840 | 109,655 |
| Total guest cycles in selected corpus | 5,178,733,792 | 5,178,733,792 |

The added 3,017 observed starts reduce interpreted ROM cycles by 99.155%.
The remaining ROM fallback is 0.00212% of guest cycles, concentrated at the
seeded instructions crossing 4 KiB program views: `4k:10:8FFF`, `4k:12:AFFF`, and
`4k:15:9FFF`. The self-modifying stack-page sound trampoline at `$0191/$0194`
also remains interpreted. Neither residual is a missing game-content handler.
Measured native coverage is 99.87537%; interpreted RAM accounts for 6,344,520
cycles (0.12251%) in this corpus.
No migration or general save-state compatibility is promised; snapshots remain
specific to a build.

## Widescreen and release checks

See [WIDESCREEN.md](WIDESCREEN.md) for the eight-round geometry, stock identity,
native/interpreter parity, save/load, Fit, viewport activation, room/death/pause,
and signed margin-sprite checks. Real catalogs pass with the feature disabled
by default and enabled through their stored options. Anchored activation matches

The first-run launcher, verified-ROM dashboard, settings and controller screens
were visually inspected in a hidden software-rendered session. The validator
checked that every owned window stayed hidden and that OpenGL came from private
Mesa DLLs. Configuration and caches stayed on G:. Defaults are windowed mode,
audio enabled and volume 100. Private software-renderer DLLs stay outside the
release archive.

The non-trace release round matrix has 88 checks. The original campaign
qualification recorded 385 passing segments at 32:9 using Classic activation
and the Centered camera:
machine state and native hashes/pictures match stock,
and native/interpreter presentation pictures and complete states match exactly.
The final driver also passes a fresh round-7 room/optional-guardian/exit chain
at 32:9 with parity enabled.

Owner playtest feedback changed the widescreen defaults to Viewport activation
and the Anchored stage camera. This profile deliberately changes enemy timing;
the stock-identity corpus above uses its explicit original profile. The new
default regression checks pass on all eight 900-frame round routes, covering
wider activation, unique spawn columns, a fixed centered HUD, native/interpreter
parity and current-build save/load. The exact 1992x720 Fit reproduction and a
right-edge checkpoint have no outside-level void. All 44 door-room checkpoints
plus the final-boss checkpoint keep centered native composition and stock machine
state/hashes, with full native/interpreter parity. The owner playtested the
updated behavior and confirmed it looked good.
The updated release also passes the full 88-check rendering matrix and all 16
real-catalog checks, including enabled features with the new option defaults.
Their evidence is in `wide-evidence/owner-fix/matrix` and `catalog` in the
repository workspace.
The follow-up removes the activation and camera controls entirely. Aspect is
the only setting. All eight 180-frame round routes match the accepted build's
hashes, native/presentation pictures and full states byte for byte; interpreter
and save/load checks pass too. The updated matrix has 88 passing checks, the
catalog has 17 (including the Aspect-only schema), presentation cadence has two,
and three hidden launcher cases pass. The real Mods screen was visually checked
to contain only Aspect. This follow-up totals 123 passing regression records.

The updated archive is
`release/MonsterParty-windows-x64-20261023-aspect-only.zip` (36 entries):
SHA256 `01AA2048D6219B2E352CAD7936A8BF4AB86979A3EE93CBFD5547520D89A412C1`.
Its executable matches the tested non-trace binary. The archive includes the
recomp-ui, font/image and dependency notices, and contains no ROM, player data,
test software renderer, or either forbidden loading-mod package.
The earlier `MonsterParty-windows-x64.zip` is retained as the original release;
it still has the earlier Classic/Centered defaults.

## Release 0.1.0

The product release moves game integrations to `src/`, keeps developer notes
under `docs/development/`, and adds three unaltered gameplay captures to the
front page. PNG compression preserves every pixel.

The Windows release passes 88 rendering records, 17 real-catalog records and
three hidden launcher cases. The Linux AppImage is built with GCC 11 on Ubuntu
22.04 and SDL2 2.30.12. On Ubuntu 24.04, all eight 120-frame round routes match
Windows per-frame hashes (ignoring CRLF/LF), native pictures and wide pictures.
Each also passes native/interpreter full-state parity and a current-build
mid-route save/load replay. No cross-build save-state compatibility is promised.

Linux first-run, verified-ROM and Aspect-only Mods screens were visually checked
under Xvfb. A stub native picker verifies the launcher's real file-selection
handoff without opening a desktop dialog; it receives the host library
environment. A forced runtime refresh preserves settings, ROM selection, mod
choices and sentinel user files. The package deliberately uses the host C++
runtime: bundling GCC 11's older library prevented newer Mesa drivers from loading.

Evidence is in `G:/Temp/Codex/MonsterPartyNESRecomp/release-010-evidence/`.
The release archives contain player instructions, launcher artwork and notices,
with no ROMs, player files, test renderers or loading-speed mod packages.

## Evidence

The main evidence root is `G:/Temp/Codex/MonsterPartyNESRecomp/`:

- `coverage/dev8`: round 1-5 and 8 chains; preliminary round-7 branch excluded
  from the selected corpus.
- `coverage/maze4/round7`, `coverage/round6final/round6`: complete maze audits.
- `coverage/cases1`, `coverage/ending1`, `coverage/ending1-sheet.png`: extra cases,
  final boss, story and credits.
- `coverage/replay1`, `coverage/replay-title1`, `coverage/replay-extra1`: post-seed
  native/interpreter and recorded-build comparisons.
- `coverage/replay-wide-core2`, `coverage/replay-wide-extra2`,
  `coverage/replay-wide-maze2`: complete selected 32:9 parity corpus.
- `wide/matrix1`, `wide/catalog1`, `wide/viewport-all`, `wide/viewport-save1`,
  `wide/scenes3`: widescreen acceptance evidence.
- `wide/defaults-owner1`, `wide/defaults-owner2`, `wide/defaults-edges-final`:
  updated defaults, HUD and centered-arena regressions. `owner-boss-inputs.json`
  retains the exact 44 door-room input paths.
- `ui-evidence1`: launcher pictures, settings, loaded-module and hidden-window checks.

`evidence/preseed-maze` in the repository workspace supplies the matching old
executable runs for the final round-6/7 routes. `wide-evidence/anchored-final` and
`wide-evidence/far-sprite-final` retain anchored regressions. Generated states,
images, audio, ROM data and diagnostic logs are ignored and are not release files.
The 16:9/21:9/32:9 round-start and scrolled contact sheets are in
`wide-evidence/contact-points/starts.png` and `scrolled.png`.
