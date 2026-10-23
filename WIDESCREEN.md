# Adaptive widescreen

The `monster-party.enhancement.widescreen` package is disabled by default.
Enable it in Display, then choose Fit, 16:9, 21:9 or 32:9. Fit responds to the
drawable aspect; a narrow window retains the native 256-pixel picture. The fixed
presets produce 426, 560 and 854 pixels at the game's 240-line presentation height.

Scrolling terrain in the margins is decoded from the current area's ROM map,
metatiles, attributes and CHR banks. Native pixels pass through. The original
per-object sprite drawer supplies signed sprite pieces for the margins; pieces
are latched with the game's OAM DMA and serialized with current-build snapshots.
The bottom HUD stays centered and its background extends across the picture.
Single-screen rooms use backdrop margins. Title/round cards and game-over scenes
retain the native picture. The game's split-line artifact at line 192 remains.

Viewport activation is the widescreen default: it activates authored enemies
across the wider view and keeps them alive there. The game has only three
ordinary enemy slots, so this can change timing, difficulty and which enemies fit
in those slots. The spawn ledger suppresses a second activation when an enemy's
column later reaches the native edge. Original spawning/culling remains available
as the Classic option. Boss-room spawning and culling remain original.

The default Anchored camera shifts the scrolling playfield near area edges to
avoid showing space outside the level. The HUD remains independently centered.
Boss arenas and single-screen rooms retain the native centered composition;
the guardian-area flag explicitly excludes arenas from stage-edge anchoring.
The optional Centered camera preserves the original screen's centered placement.
Viewport activation computes that camera directly from the simulation, so its
behavior does not depend on presentation frequency. A regression compares every
frame, every 60 frames, and final-only composition, plus interpreter parity.
An anchored fixture at X=740 also checks sprites across the full one-sided margin.

## Validation

The headless 900-frame matrix covers all eight round starts, with right/left
movement, jumps and bat swings. The retained pre-mod executable and the WIP build
match byte for byte in native frame hashes, PNGs and complete states when the mod
is disabled or explicitly off. Enabled classic rendering preserves machine state
and hashes; the added presentation record is the only additional state chunk.

All eight rounds passed 16:9, 21:9 and 32:9 terrain-opacity checks, with no isolated
call failures or packet overflow. At 32:9, native and interpreter hashes, native
PNGs, presentation PNGs and complete states match. Mid-route save/load replay
matches the uninterrupted final state, presentation and hash suffix. Fit cases
cover 1280x720, 3840x1080 and 1024x960 drawable sizes.

The viewport 900-frame matrix also matches native/interpreter hashes, both PNGs
and states on all eight rounds. Ordinary enemies spawned and were retained in
margins in scrolling rounds; the round-6 route and single-screen round 7 did not
exercise new viewport spawns. Suppressed native-edge activations were observed.

Additional retained scene cases cover empty rooms, a projectile-boss room,
game-over and pause. A journaled fixture freezes an existing enemy at screen
X=-40: the margin sprite appears while the native PNG stays unchanged, matches
the interpreter, and leaves no stale packet after removal. Guardian-room speech
windows are native overlays and are excluded from terrain-decoder diagnostics;
their margins use backdrop rather than decoded terrain.

Run `tests/widescreen/validate.py` for the round matrix and
`tests/widescreen/scenes.py` for checkpoint and margin-sprite checks. Commands,
routes, native/presentation pictures, full states and JSON diagnostics are retained
under the specified non-C: evidence directory. `tests/coverage/replay.py
--widescreen 32:9` adds stock-preserving Classic/Centered presentation parity
to recorded campaign routes.

`tests/widescreen/defaults.py` checks the owner playtest regressions using the
actual widescreen defaults: wider enemy activation, no duplicate spawn columns,
native/interpreter and save/load parity, an unchanged centered HUD, and centered
guardian rooms with stock machine behavior. It also reproduces the 1992x720 Fit
window from the owner screenshot and compares the leftmost native playfield
pixels directly, so a black outside-level margin cannot pass as anchored terrain.
