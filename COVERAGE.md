# Monster Party (USA) validation

ROM payload CRC32 `02B9E7C2`; NESRecomp `a76140c`; recomp-ui `7c635c6`.
All runs were headless or explicitly hidden, with speaker output muted. No
visible game/launcher window was opened. Fixtures and commands are retained.

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
across every-frame, occasional and final-only composition, and an X=740 sprite
fixture covers its full one-sided margin.

The first-run launcher, verified-ROM dashboard, settings and controller screens
were visually inspected in a hidden software-rendered session. The validator
checked that every owned window stayed hidden and that OpenGL came from private
Mesa DLLs. Configuration and caches stayed on G:. Defaults are windowed mode,
audio enabled and volume 100. The software-renderer DLLs are test tools only.

The non-trace release binary passes all 88 round-matrix checks. Final 32:9
campaign replay is running; its completion is required before the validation
branch is merged into master.

## Evidence

The main evidence root is `G:/Temp/Codex/MonsterPartyNESRecomp/`:

- `coverage/dev8`: round 1-5 and 8 chains; preliminary round-7 branch excluded
  from the selected corpus.
- `coverage/maze4/round7`, `coverage/round6final/round6`: complete maze audits.
- `coverage/cases1`, `coverage/ending1`, `coverage/ending1-sheet.png`: extra cases,
  final boss, story and credits.
- `coverage/replay1`, `coverage/replay-title1`, `coverage/replay-extra1`: post-seed
  native/interpreter and recorded-build comparisons.
- `wide/matrix1`, `wide/catalog1`, `wide/viewport-all`, `wide/viewport-save1`,
  `wide/scenes3`: widescreen acceptance evidence.
- `ui-evidence1`: launcher pictures, settings, loaded-module and hidden-window checks.

`evidence/preseed-maze` in the repository workspace supplies the matching old
executable runs for the final round-6/7 routes. `wide-evidence/anchored-final` and
`wide-evidence/far-sprite-final` retain anchored regressions. Generated states,
images, audio, ROM data and diagnostic logs are ignored and are not release files.
The 16:9/21:9/32:9 round-start and scrolled contact sheets are in
`wide-evidence/contact-points/starts.png` and `scrolled.png`.
