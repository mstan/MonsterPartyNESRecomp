"""Cheat-assisted Monster Party (USA) coverage campaign on the cycle backend.

Each round is played as one chain of deterministic headless segments: round
select on the original ROUND START screen, a warp to every door of the round's
door table, the guardian fight or room visit behind it, the walk back out, and
finally the original round exit. Warps are journaled work-RAM fixtures
(tools/cycstate.py); fights use the developer assists in mp_assist.c (life
refill, guardians fall to the next landed hit). Every state the game reaches
is reached through its own code: door transitions (7:D949), the area loader,
guardian defeat (5:8D22) and the round-clear path (4:830A).

  python tests/coverage/campaign.py --tag baseline [--rounds 1 2] [--parity]

Native runs append --miss-log/--capture-log to <tag>/misses.txt; with --parity
every segment is replayed with --interp-only and its hash, picture and full
state must match. Evidence lands in evidence/coverage/<tag>/ (gitignored).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import cycstate  # noqa: E402
import mp_doors  # noqa: E402
import mp_map  # noqa: E402
import mp_run  # noqa: E402

GUARDS = [3, 3, 3, 3, 2, 1, 2, 3]       # 4:$945B, guardians each round needs
TITLE_ROUTE = '0 -\n300 START\n306 -\n500 START\n506 -\n'
WATCH = (0x97, 0x4F, 0x6A, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x9E, 0x032F, 0x50, 0x25, 0x03CB, 0x03D6)


class Chain:
    """One round's sequence of segments; each starts from the previous end state."""

    def __init__(self, out, args, name):
        self.out, self.args, self.name = Path(out), args, name
        self.out.mkdir(parents=True, exist_ok=True)
        self.state, self.n, self.log = None, 0, []

    def seg(self, label, frames, route_fn=None, assist='life,guardians', pokes=()):
        """Run `frames` frames; route_fn(first_frame) returns input lines (absolute frames)."""
        first = mp_run.start_frame(self.state)
        route = '\n'.join(route_fn(first)) if route_fn else ''
        name = f'{self.n:03d}-{label}'
        self.n += 1
        r = mp_run.run(self.out, name, frames, state=self.state, route=route, assist=assist, pokes=pokes)
        row = dict(segment=name, first=first, end=r['end'], ram={f'{a:04X}': r['ram'][a] for a in WATCH},
                   start_state=str(self.state) if self.state else None)
        if self.args.parity:
            i = mp_run.run(self.out / 'interp', name, frames, state=self.state, route=route, assist=assist,
                           pokes=pokes, interp=True)
            row['parity'] = {ext: Path(r['state']).with_suffix(ext).read_bytes() ==
                             Path(i['state']).with_suffix(ext).read_bytes() for ext in ('.hash', '.png', '.cycstate')}
            if not all(row['parity'].values()):
                raise SystemExit(f'{self.name} {name}: native/interpreter mismatch {row["parity"]}')
        self.log.append(row)
        self.state = Path(r['state'])
        mp_run.show(r, 0x4F, 0x6A, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x50, 0x25, 0x3CB, 0x3D6)
        return r

    def fixture(self, label, writes, purpose):
        dest = self.out / f'{self.n:03d}-{label}.cycstate'
        self.n += 1
        cycstate.fixture(self.state, dest, writes, purpose)
        self.log.append(dict(fixture=dest.name, writes={f'{a:04X}': v for a, v in writes.items()}, purpose=purpose))
        self.state = dest

    def ram(self):
        return cycstate.ram(Path(self.state).read_bytes())


def mash(first, frames):
    """Dismiss the room text, then bat swings every 8 frames while pacing both ways,
    jumping now and then: reaches most guardians and their projectiles."""
    lines = [f'{first} A', f'{first + 6} -', f'{first + 40} A', f'{first + 46} -']
    for k, f in enumerate(range(first + 80, first + frames - 8, 8)):
        d = 'RIGHT' if (k // 8) % 2 == 0 else 'LEFT'
        jump = ' A' if k % 15 == 14 else ''
        lines += [f'{f} {d} B{jump}', f'{f + 4} {d}']
    return lines + [f'{first + frames - 8} -']


def warp_writes(world_x, row, request_door):
    cam = max(0, min(world_x - 0x80, 0xF00))
    w = {0x50: cam >> 8, 0x25: cam & 0xFF, 0x03D6: (world_x - cam + 8) & 0xFF, 0x040D: 0, 0x03CB: row * 16 + 4}
    if request_door:
        w[0x53] = 1
    return w


def leave(chain, label):
    """Walking off the room's left edge takes its return door (area 8-15 tables)."""
    chain.seg(f'{label}-leave', 300, lambda f: [f'{f} LEFT', f'{f + 150} -'])


def return_point(chain, label, world_x, row, purpose):
    """Inside a room: move the game's saved return point ($75-$7A, stored by
    7:D9DC) so that walking out redraws the round with Mark at world_x/row."""
    cam = max(0, min(world_x - 0x80, 0xF00))
    chain.fixture(label, {0x76: cam >> 8, 0x78: cam & 0xFF, 0x79: row * 16 + 4, 0x7A: (world_x - cam + 8) & 0xFF},
                  purpose)


def is_room(d, area):
    return d['dest_area'] not in (area, 'return')


def play_round(n, args, root):
    area = n - 1
    chain = Chain(root / f'round{n}', args, f'round{n}')
    select = root / f'round{n}-select.cycstate'
    if not select.exists():
        cycstate.fixture(args.title_state, select, {0x97: n - 1},
                         f'Round {n}: $97 on the original ROUND START screen before START runs 4:$941B')
    chain.state = select
    chain.seg('start', 400, lambda f: [f'{f + 10} START', f'{f + 16} -'])
    start_state = chain.state
    walk = chain.seg('walk', 1200, lambda f: sum(([f'{g} RIGHT', f'{g + 20} RIGHT A', f'{g + 36} RIGHT']
                                                    for g in range(f, f + 1200, 45)), []))
    results = dict(round=n, doors=[], walk_end_page=walk['ram'][0x50])
    chain.state = start_state
    exit_row, exit_x = max((r, x) for k, r, x in mp_map.find(start_state, kinds=(7,)))
    table = mp_doors.areas()[area]['doors']
    doors = [d for d in table if not args.doors or d['index'] in args.doors]
    first_room = next(d for d in table if is_room(d, area))
    in_room = False

    def enter(d, how):
        label = f'door{d["index"]:02d}'
        if how == 'up':
            chain.seg(f'{label}-enter', 240, lambda f: [f'{f + 20} UP', f'{f + 26} -'])
        else:
            chain.fixture(label, warp_writes(d['world_x'][0], d['row'], True),
                          f'Round {n} door {d["index"]}: Mark at its table position, door request $53 (7:D949)')
            chain.seg(f'{label}-enter', 240)

    def visit_room(d, label):
        guard_before = chain.ram()[0x58]
        # 7:D99E: bit 7 of $52 names a guardian; round 6's single guardian room is content 0.
        counted = bool(d['flag_52'] & 0x80) and (d['param_6C'] != 0 or area == 5) and guard_before > 0
        frames = args.fight_frames if counted else 400
        for k in range(args.fight_tries if counted else 1):
            r = chain.seg(f'{label}-room{k}', frames, lambda f: mash(f, frames))
            if r['ram'][0x58] < guard_before:
                break
        return counted

    for d in doors:
        here = chain.ram()
        label = f'door{d["index"]:02d}'
        if in_room:
            return_point(chain, f'{label}-return-point', d['world_x'][0], d['row'],
                         f'Round {n}: walk out of the room in front of door {d["index"]}')
            leave(chain, label)
            back = chain.ram()
            if back[0x4F] != area:
                raise SystemExit(f'round {n}: walking out did not return to area {area}')
            # Mark keeps walking while LEFT is still held after the redraw; put
            # him back on the door column (screen X only, camera untouched).
            cam = (back[0x50] << 8) | back[0x25]
            chain.fixture(f'{label}-nudge', {0x03D6: (d['world_x'][0] - cam + 8) & 0xFF, 0x03CB: d['row'] * 16 + 4},
                          f'Round {n}: Mark back onto door {d["index"]} column after walking out')
            enter(d, 'up')
        else:
            enter(d, 'warp')
        now = chain.ram()
        if is_room(d, area):
            entered = now[0x4F] == d['dest_area']
        else:
            entered = (now[0x50], now[0x25], now[0x3CB]) != (here[0x50], here[0x25], here[0x3CB])
        row = dict(door=d['index'], dest_area=d['dest_area'], guardian=d['guardian'], room=d['param_6C'],
                   reached_area=now[0x4F], entered=entered)
        if not entered:
            raise SystemExit(f'round {n}: door {d["index"]} did not take Mark anywhere')
        in_room = now[0x4F] != area
        if in_room:
            row['counted'] = visit_room(d, label)
        row['guardians_left'] = chain.ram()[0x58]
        results['doors'].append(row)
    if args.clear:
        if chain.ram()[0x58]:
            raise SystemExit(f'round {n}: {chain.ram()[0x58]} guardians left before the exit; not forcing it')
        if not in_room:
            enter(first_room, 'warp')
            visit_room(first_room, 'exit-room')
        return_point(chain, 'exit-return-point', exit_x, exit_row,
                     f'Round {n}: walk out of the room in front of the round exit')
        leave(chain, 'exit')
        r = chain.seg('exit', 900, lambda f: [f'{f + 20} UP', f'{f + 26} -', f'{f + 400} START', f'{f + 406} -'])
        results['after_exit'] = dict(round=r['ram'][0x97] + 1, area=r['ram'][0x4F], guardians=r['ram'][0x58])
    (chain.out / 'chain.json').write_text(json.dumps(dict(results=results, segments=chain.log), indent=1) + '\n', newline='\n')
    print(json.dumps(results))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--rounds', type=int, nargs='*', default=list(range(1, 9)))
    ap.add_argument('--doors', type=int, nargs='*')
    ap.add_argument('--parity', action='store_true')
    ap.add_argument('--clear', action='store_true', help='exit through the original round exit after the last door')
    ap.add_argument('--fight-frames', type=int, default=1200)
    ap.add_argument('--fight-tries', type=int, default=4)
    args = ap.parse_args()
    root = ROOT / 'evidence' / 'coverage' / args.tag
    root.mkdir(parents=True, exist_ok=True)
    args.title_state = root / 'title-1000.cycstate'
    if not args.title_state.exists():
        r = mp_run.run(root, 'title', 1000, route=TITLE_ROUTE, assist=None)
        Path(r['state']).replace(args.title_state)
    summary = [play_round(n, args, root) for n in args.rounds]
    (root / f'summary-{"-".join(map(str, args.rounds))}.json').write_text(json.dumps(summary, indent=1) + '\n', newline='\n')


if __name__ == '__main__':
    main()
