"""Owner regressions: wide enemies, stage edges, fixed HUD and centered arenas."""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import cycstate
import mp_run
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import machine, route


def main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    records = []

    def record(name, **checks):
        records.append(dict(case=name, checks=checks, passed=all(checks.values())))
        (args.output / 'results.json').write_text(json.dumps(records, indent=1) + '\n', newline='\n')
        print(name, checks, flush=True)
        if not all(checks.values()):
            raise AssertionError(name)

    def run(name, state, frames, extra=(), interp=False, text=None, wide=True):
        stem = args.output / name
        options = ['--present-out', str(stem.with_suffix('.present.png'))]
        if wide:
            options += ['--widescreen', '32:9', '--widescreen-report', str(stem.with_suffix('.jsonl'))]
        r = mp_run.run(args.output, name, frames, state=state,
                       route=route(mp_run.start_frame(state), frames) if text is None else text,
                       assist='life', extra=options + list(extra), exe=args.exe, interp=interp)
        r['stem'] = stem
        r['rows'] = [json.loads(s) for s in stem.with_suffix('.jsonl').read_text().splitlines()] if wide else []
        return r

    def same(a, b, ext):
        return a['stem'].with_suffix(ext).read_bytes() == b['stem'].with_suffix(ext).read_bytes()

    def native_crop(r, hud_only=False):
        picture = Image.open(r['stem'].with_suffix('.present.png')).convert('RGBA')
        native = Image.open(r['stem'].with_suffix('.png')).convert('RGBA')
        x0 = (picture.width - 256) // 2
        top = 192 if hud_only else 0
        return picture.crop((x0, top, x0 + 256, 240)).tobytes() == native.crop((0, top, 256, 240)).tobytes()

    def playfield_at(r, x0):
        picture = Image.open(r['stem'].with_suffix('.present.png')).convert('RGBA')
        native = Image.open(r['stem'].with_suffix('.png')).convert('RGBA')
        return picture.crop((x0, 0, x0 + 256, 192)).tobytes() == native.crop((0, 0, 256, 192)).tobytes()

    for n in args.rounds:
        state = ROOT / 'evidence' / 'rounds' / f'round{n}-start.cycstate'
        first = mp_run.start_frame(state)
        middle = args.output / f'round{n}-middle.cycstate'
        ram_log = args.output / f'round{n}.ram'
        r = run(f'round{n}', state, args.frames,
                extra=['--save-state', f'{first + args.frames // 2 - 1}:{middle}', '--mp-ram-log', str(ram_log)])
        i = run(f'round{n}-interp', state, args.frames, interp=True)
        cut = first + args.frames // 2
        lines = route(first, args.frames).splitlines()
        prior = [line for line in lines if int(line.split()[0]) < cut][-1]
        suffix = f'{cut} {prior.split(" ", 1)[1]}\n' + '\n'.join(line for line in lines if int(line.split()[0]) >= cut)
        replay = run(f'round{n}-reload', middle, args.frames - args.frames // 2, text=suffix)
        tail = replay['stem'].with_suffix('.hash').read_bytes().splitlines()
        ram = ram_log.read_bytes()
        duplicate = False
        margin_enemy = False
        for at in range(0, len(ram), 2048):
            active = [k for k in range(3) if ram[at + 0x3c6 + k] & 128]
            indices = [ram[at + 0x408 + k] for k in active]
            duplicate |= len(indices) != len(set(indices))
            for k in active:
                x = int.from_bytes(bytes((ram[at + 0x3dc + k], ram[at + 0x413 + k])), 'little', signed=True)
                margin_enemy |= x < 0 or x >= 256
        checks = {f'parity{ext}': same(r, i, ext) for ext in ('.hash', '.png', '.present.png', '.cycstate')}
        checks.update(defaults=all(row['viewport'] and row['anchored'] for row in r['rows']),
                      centered_hud=native_crop(r, hud_only=True),
                      no_duplicate_columns=not duplicate,
                      failures=all(row['failures'] == row['mod_failures'] == row['overflow'] == row['terrain_errors'] == 0 for row in r['rows']),
                      reload_state=same(r, replay, '.cycstate'), reload_picture=same(r, replay, '.present.png'),
                      reload_hash=r['stem'].with_suffix('.hash').read_bytes().splitlines()[-len(tail):] == tail)
        if n == 1:
            checks['enemy_in_margin'] = margin_enemy and r['rows'][-1]['spawns'] > 0
        record(f'round{n}', **checks)
        print('counters', r['rows'][-1], 'margin_enemy', margin_enemy, flush=True)
        if n == 1:
            # Exact drawable aspect of the owner's 1992x720 screenshot. At the
            # start, the tree must meet the left edge while the HUD stays put.
            edge = run('owner-fit', state, 120, text='',
                       extra=['--widescreen', 'fit', '--present-size', '1992x720'])
            record('owner-fit', width=all(row['width'] == 664 for row in edge['rows']),
                   no_left_void=all(row['camera'] == 0 for row in edge['rows']) and playfield_at(edge, 0),
                   centered_hud=native_crop(edge, hud_only=True),
                   wide_enemies=edge['rows'][-1]['spawns'] > 0)

    if args.right_edge:
        edge = run('right-edge', args.right_edge, 120, text='')
        picture = Image.open(edge['stem'].with_suffix('.present.png')).convert('RGBA')
        native = Image.open(edge['stem'].with_suffix('.png')).convert('RGBA')
        record('right-edge', at_level_end=all(row['camera'] == row['last_page'] * 256 for row in edge['rows']),
               no_right_void=picture.crop((picture.width - 128, 0, picture.width, 192)).tobytes() == native.crop((128, 0, 256, 192)).tobytes(),
               centered_hud=native_crop(edge, hud_only=True))

    for index, state in enumerate(args.boss_states):
        data = cycstate.ram(state.read_bytes())
        if not data[0x52] & 128:
            raise AssertionError(f'Not a guardian arena: {state}')
        name = f'arena{index:02d}'
        r = run(name, state, 120, text='')
        base = run(name + '-stock', state, 120, text='', wide=False)
        i = run(name + '-interp', state, 120, text='', interp=True)
        record(name, centered=all(row['scene'] == 1 for row in r['rows']),
               native_picture=native_crop(r), machine=machine(r['state']) == machine(base['state']),
               stock_hash=same(r, base, '.hash'),
               **{f'parity{ext}': same(r, i, ext) for ext in ('.hash', '.png', '.present.png', '.cycstate')})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--rounds', type=int, nargs='*', default=list(range(1, 9)))
    ap.add_argument('--frames', type=int, default=900)
    ap.add_argument('--boss-states', type=Path, nargs='*', default=[])
    ap.add_argument('--right-edge', type=Path)
    main(ap.parse_args())
