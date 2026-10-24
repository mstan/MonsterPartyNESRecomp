"""Curated mods: real cartridge effects, inert defaults, native parity and replay.

Runs silently in separate catalogs. --require-probes uses the optional
MONSTERPARTY_MOD_TESTS build to exercise landed-hit and damage routines directly.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import mp_run
import cycstate

CHEATS = 'monster-party.cheats.game-genie'
RESTORE = 'monster-party.content.prototype-restoration'
WIDE = 'monster-party.enhancement.widescreen'
BOOT = '0 -\n300 START\n306 -\n500 START\n506 -\n1010 START\n1016 -\n'


def catalog(path, features, restoration=False, wide=False):
    shutil.copytree(ROOT / 'mods/preloaded/packages', path / 'packages', dirs_exist_ok=True)
    packages = {CHEATS: features}
    if restoration:
        packages[RESTORE] = {'restoration': {}}
    if wide:
        packages[WIDE] = {'widescreen': {'aspect': '32-9'}}
    lines = []
    for package, selected in packages.items():
        lines += ['[[package]]', f'id = "{package}"', 'version = "1.0.0"']
        for feature, values in selected.items():
            lines += ['[[feature]]', f'package_id = "{package}"', f'id = "{feature}"', 'enabled = true']
            if values:
                lines += ['[feature.values]'] + [f'{key} = "{value}"' for key, value in values.items()]
    (path / 'state.toml').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    return path


def validate(args):
    args.out.mkdir(parents=True, exist_ok=True)
    results = []

    def record(name, **checks):
        results.append(dict(case=name, checks=checks))
        (args.out / 'results.json').write_text(json.dumps(results, indent=2) + '\n', newline='\n')
        print(name, checks, flush=True)
        assert all(checks.values()), name

    def run(name, cat=None, frames=1400, state=None, route=BOOT, interp=False, extra=()):
        folder = args.out / name
        options = ['--present-out', str(folder / 'result.present.png'), *extra]
        if cat:
            options += ['--mods-root', str(cat)]
        # Reuse the independently validated 650-frame boot evidence when
        # extending that run through the round card into actual gameplay.
        previous = folder / 'result.cycstate'
        if args.resume_boot and state is None and frames == 1400 and previous.exists() and mp_run.start_frame(previous) == 650:
            state = folder / 'boot-650.cycstate'
            shutil.copyfile(previous, state)
            frames -= 650
            route = '650 -\n' + '\n'.join(line for line in route.splitlines() if int(line.split()[0]) >= 650) + '\n'
        return mp_run.run(folder, 'result', frames, state=state, route=route, interp=interp,
                          extra=options, exe=args.exe, harvest=False)

    def same(a, b, ext):
        return Path(a['state']).with_suffix(ext).read_bytes() == Path(b['state']).with_suffix(ext).read_bytes()

    stock = run('stock')
    disabled = run('disabled', catalog(args.out / 'catalog-disabled', {}))
    record('disabled-is-stock', **{ext: same(stock, disabled, ext) for ext in ('.hash', '.png', '.cycstate')})
    cases = [
        ('invincibility', {'invincibility': {}}, False, False),
        ('one-hit-enemies', {'one-hit': {'targets': 'enemies'}}, False, False),
        ('one-hit-guardians', {'one-hit': {'targets': 'guardians'}}, False, False),
        ('one-hit-both', {'one-hit': {'targets': 'both'}}, False, False),
        ('endless-bert', {'endless-bert': {}}, False, False),
        ('energy-normal', {'energy': {'amount': 'normal'}}, False, False),
        ('energy-boosted', {'energy': {'amount': 'boosted'}}, False, False),
        ('energy-super', {'energy': {'amount': 'super'}}, False, False),
        ('speed-2', {'speed': {'amount': '2'}}, False, False),
        ('speed-4', {'speed': {'amount': '4'}}, False, False),
        ('jump-high', {'jump': {'height': 'high'}}, False, False),
        ('jump-extra', {'jump': {'height': 'extra'}}, False, False),
        ('restoration', {}, True, False),
        ('combined', {'invincibility': {}, 'one-hit': {'targets': 'both'}, 'endless-bert': {},
                      'energy': {'amount': 'super'}, 'speed': {'amount': '2'}, 'jump': {'height': 'high'}}, True, True),
    ]
    cases += [(f'round-{n}', {'round': {'number': str(n)}}, True, True) for n in range(1, 9)]
    runs = {'stock': stock}
    for name, features, restoration, wide in cases:
        cat = catalog(args.out / f'catalog-{name}', features, restoration, wide)
        native = run(name, cat)
        interp = run(name + '-interp', cat, interp=True)
        checks = {ext: same(native, interp, ext) for ext in ('.hash', '.png', '.present.png', '.cycstate')}
        log = Path(native['log']).read_text()
        # Hardware cycles are absolute after a loaded snapshot, while dispatch
        # counters cover only this process. Compare the dispatch counters.
        ram_cycles = re.search(r'RAM (\d+) \(', log)
        interpreted = (native['interp_rom'] or 0) + (int(ram_cycles[1]) if ram_cycles else 0)
        checks['native_execution'] = native['native'] > 0 and interpreted < native['native'] * .02
        probe = re.search(r'mod-probe: life=(\d+) enemy_hp=(\d+) enemy_dead=(\d+) guardian_hp=(\d+) bert=(\d+) timer=(\d+)', log)
        if probe:
            target = features.get('one-hit', {}).get('targets', '')
            expected = (12 if 'invincibility' in features else 11,
                        0 if target in ('enemies', 'both') else 2,
                        1 if target in ('enemies', 'both') else 0,
                        0 if target in ('guardians', 'both') else 4,
                        128 if 'endless-bert' in features else 0,
                        0 if 'endless-bert' in features else 1)
            checks['cartridge_effects'] = tuple(map(int, probe.groups())) == expected
        elif args.require_probes:
            checks['cartridge_effects'] = False
        if 'energy' in features:
            checks['starting_energy'] = native['ram'][0x9E] == {'normal': 12, 'boosted': 24, 'super': 44}[features['energy']['amount']]
        if 'round' in features:
            checks['starting_round'] = native['ram'][0x97] == int(features['round']['number']) - 1
        record(name, **checks)
        runs[name] = native

    # Measure motion through the actual controller/update path on an unobstructed
    # part of round 1. Starting snapshots were produced with the same policy.
    def world(ram): return ram[0x50] * 256 + ram[0x25] + ram[0x3D6] + 256 * ram[0x40D]
    moves = []
    for name in ('stock', 'speed-2', 'speed-4'):
        state = Path(runs[name]['state']); first = mp_run.start_frame(state)
        cat = None if name == 'stock' else args.out / f'catalog-{name}'
        moved = run(name + '-motion', cat, frames=8, state=state, route=f'{first} RIGHT\n')
        moves.append(world(moved['ram']) - world(runs[name]['ram']))
    record('walking-speed', normal=moves[0] > 0, twice=moves[1] == moves[0] * 2, four_times=moves[2] == moves[0] * 4)
    heights = []
    for name in ('stock', 'jump-high', 'jump-extra'):
        state = Path(runs[name]['state']); first = mp_run.start_frame(state)
        cat = None if name == 'stock' else args.out / f'catalog-{name}'
        ramfile = args.out / f'{name}-jump.ram'
        jumped = run(name + '-jump', cat, frames=32, state=state, route=f'{first} A\n', extra=['--mp-ram-log', str(ramfile)])
        raw = ramfile.read_bytes()
        heights.append(min(raw[i+0x3CB] for i in range(0, len(raw), 2048)))
    record('jump-height', high=heights[1] < heights[0], extra=heights[2] < heights[1])

    # Same-policy save/load replay with restoration, cheats, sprites and margins.
    cat = args.out / 'catalog-combined'
    start = Path(runs['combined']['state']); first = mp_run.start_frame(start)
    mid = args.out / 'combined-middle.cycstate'
    whole = run('combined-whole', cat, frames=180, state=start,
                route=f'{first} RIGHT\n{first+60} RIGHT A\n{first+100} RIGHT\n',
                extra=['--save-state', f'{first+89}:{mid}'])
    replay = run('combined-replay', cat, frames=90, state=mid,
                 route=f'{first+90} RIGHT A\n{first+100} RIGHT\n')
    record('combined-save-load', **{ext: same(whole, replay, ext) for ext in ('.png', '.present.png', '.cycstate')},
           hashes=Path(whole['state']).with_suffix('.hash').read_bytes().splitlines()[90:] ==
                  Path(replay['state']).with_suffix('.hash').read_bytes().splitlines())
    for restored in (False, True):
        cat = args.out / ('catalog-restoration' if restored else 'catalog-disabled')
        run('title-restored' if restored else 'title-stock', cat, frames=250, route='')
    record('restored-title', changed=not same({'state': str(args.out/'title-stock/result.cycstate')},
                                            {'state': str(args.out/'title-restored/result.cycstate')}, '.png'))
    print('Motion deltas:', moves, 'Jump Y minima:', heights, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--require-probes', action='store_true')
    parser.add_argument('--resume-boot', action='store_true')
    validate(parser.parse_args())
