"""Cheat-assisted Monster Party (USA) coverage campaign on the cycle backend.

Each round uses deterministic headless segments: round selection on the original
ROUND START screen, visits to every room, independent maze branches from a
recorded room checkpoint, and the original round exit. Optional encounters may
branch from a naturally cleared checkpoint. Warps are journaled work-RAM fixtures
(tools/cycstate.py); fights use the developer assists in mp_assist.c (life
refill, guardians fall to the next landed hit). Door transitions (7:D949), the
area loader, guardian defeat (5:8D22) and round clear (4:830A) run the original
code. Fixtures provide assisted setup, not unassisted traversal evidence.

  python tests/coverage/campaign.py --tag baseline [--rounds 1 2] [--parity]

Native runs append --miss-log/--capture-log to <tag>/misses.txt; with --parity
every segment is replayed with --interp-only and its hash, picture and full
state must match. Evidence lands in evidence/coverage/<tag>/ (gitignored).
"""
import argparse
import json
import shutil
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
WATCH = (0x97, 0x4F, 0x6A, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x9E, 0x032F, 0x50, 0x51, 0x25, 0x52, 0x53, 0x03CB, 0x03D6)


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
        extra = list(getattr(self.args, 'extra', ()))
        if getattr(self.args, 'assist', None) is not None:
            assist = self.args.assist or None
        if getattr(self.args, 'widescreen', None):
            extra += ['--widescreen', self.args.widescreen, '--present-out', str(self.out / f'{name}.present.png')]
        exe = getattr(self.args, 'exe', mp_run.EXE)
        r = mp_run.run(self.out, name, frames, state=self.state, route=route, assist=assist, pokes=pokes, extra=extra, exe=exe)
        row = dict(segment=name, first=first, end=r['end'], ram={f'{a:04X}': r['ram'][a] for a in WATCH},
                   start_state=str(self.state) if self.state else None,
                   cycles=r['cycles'], native_cycles=r['native'], interpreted_rom_cycles=r['interp_rom'])
        if self.args.parity:
            iextra = list(getattr(self.args, 'extra', ()))
            if getattr(self.args, 'widescreen', None):
                iextra += ['--widescreen', self.args.widescreen, '--present-out', str(self.out / 'interp' / f'{name}.present.png')]
            i = mp_run.run(self.out / 'interp', name, frames, state=self.state, route=route, assist=assist,
                           pokes=pokes, interp=True, extra=iextra, exe=exe)
            row['parity'] = {ext: Path(r['state']).with_suffix(ext).read_bytes() ==
                             Path(i['state']).with_suffix(ext).read_bytes() for ext in ('.hash', '.png', '.cycstate')}
            if getattr(self.args, 'widescreen', None):
                row['parity']['.present.png'] = (self.out / f'{name}.present.png').read_bytes() == (self.out / 'interp' / f'{name}.present.png').read_bytes()
            if not all(row['parity'].values()):
                raise SystemExit(f'{self.name} {name}: native/interpreter mismatch {row["parity"]}')
        self.log.append(row)
        self.state = Path(r['state'])
        self.checkpoint()
        mp_run.show(r, 0x4F, 0x6A, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x50, 0x25, 0x3CB, 0x3D6)
        return r

    def fixture(self, label, writes, purpose):
        dest = self.out / f'{self.n:03d}-{label}.cycstate'
        self.n += 1
        cycstate.fixture(self.state, dest, writes, purpose)
        self.log.append(dict(fixture=dest.name, writes={f'{a:04X}': v for a, v in writes.items()}, purpose=purpose))
        self.state = dest
        self.checkpoint()

    def checkpoint(self):
        (self.out / 'segments.json').write_text(json.dumps(self.log, indent=1) + '\n', newline='\n')

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


def reflect(first, frames):
    """Face the projectile boss, hold position and jump into its shot height.
    Invincibility removes knockback, so walking into the corner misses shots."""
    lines = [f'{first} RIGHT', f'{first + 1} -']
    for frame in range(first + 8, first + frames, 8):
        jump = ' A' if (frame - first) % 64 < 16 else ''
        lines += [f'{frame} B{jump}', f'{frame + 4}{jump or " -"}']
    return lines


def leave(chain, label):
    """Walking off the room's left edge takes its return door (area 8-15 tables)."""
    hold = chain.ram()[0x03D6] + 12
    chain.seg(f'{label}-leave', hold + 150, lambda f: [f'{f} LEFT', f'{f + hold} -'])
    if chain.ram()[0x5E] & 0x80:
        # UP flies as Bert. Wait for the original timer before checking a
        # door or exit as Mark; never write the transformation flag.
        chain.seg(f'{label}-bert-expiry', 3000)
        if chain.ram()[0x5E] & 0x80:
            raise SystemExit('Door audit needs Bert expiry; disable Endless Bert for this campaign')


def return_point(chain, label, world_x, row, purpose, segmented=False):
    """Inside a room: move the game's saved return point ($75-$7A, stored by
    7:D9DC) so that walking out redraws the round with Mark at world_x/row."""
    offset = world_x >> 8 if segmented else 0
    local_x = world_x - offset * 256
    cam = 0 if segmented else max(0, min(world_x - 0x80, 0xF00))
    chain.fixture(label, {0x76: cam >> 8, 0x77: offset, 0x78: cam & 0xFF, 0x79: row * 16 + 4, 0x7A: (local_x - cam + 8) & 0xFF},
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
    # Clear the rooms first. In-area maze cases branch from the resulting room
    # checkpoint, so each has a genuine room return and never requests a door
    # while unrelated live enemy tasks are left behind.
    doors.sort(key=lambda d: not is_room(d, area))
    in_room = False
    room_checkpoint = None
    clear_checkpoint = None

    def enter(d, how):
        label = f'door{d["index"]:02d}'
        if how == 'up':
            before = chain.ram()
            pad = 'DOWN' if n == 7 and d['row'] == 11 else 'UP'
            held = 90 if n == 7 and d['row'] in (0,11) else 6
            chain.seg(f'{label}-enter', 240, lambda f: [f'{f} {pad}', f'{f + held} -'])
        else:
            chain.fixture(label, warp_writes(d['world_x'][0], d['row'], True),
                          f'Round {n} door {d["index"]}: Mark at its table position, door request $53 (7:D949)')
            before = chain.ram()
            chain.seg(f'{label}-enter', 240)
        return before

    def visit_room(d, label):
        guard_before = chain.ram()[0x58]
        # 7:D99E: bit 7 of $52 names a guardian; round 6's single guardian room is content 0.
        guardian = (d['flag_52'] >> 4) & 7
        encounter = bool(d['flag_52'] & 0x80) and (d['param_6C'] != 0 or area == 5)
        counted = encounter and guard_before > 0
        frames = args.fight_frames if encounter else 400
        if n == 4 and d['param_6C'] == 1:
            chain.seg(f'{label}-dialog', 80, lambda f: [f'{f} A', f'{f+6} -', f'{f+40} A', f'{f+46} -'])
            chain.fixture(f'{label}-reflect-position', {0x03D6: 0xA0, 0x03CB: 0x94, 0x040D: 0},
                          'Stand beside the projectile boss to reflect its shots with real bat swings')
            frames = 2400
        for k in range(args.fight_tries if encounter else 1):
            if n == 4 and d['param_6C'] == 1:
                route = lambda f: reflect(f, frames)
            else:
                route = lambda f: mash(f, frames)
            r = chain.seg(f'{label}-room{k}', frames, route)
            if encounter and r['ram'][0x59 + guardian] & 0x80:
                break
        if encounter and not (chain.ram()[0x59 + guardian] & 0x80):
            raise SystemExit(f'round {n}: guardian {guardian} behind door {d["index"]} was not defeated')
        return counted

    for d in doors:
        label = f'door{d["index"]:02d}'
        if not in_room and room_checkpoint:
            source = clear_checkpoint or room_checkpoint
            chain.log.append(dict(branch=str(source), purpose='Independent maze case from the room checkpoint'))
            chain.state = source
            in_room = True
        if in_room:
            return_point(chain, f'{label}-return-point', d['world_x'][0], d['row'],
                         f'Round {n}: walk out of the room in front of door {d["index"]}', segmented=n == 7)
            leave(chain, label)
            back = chain.ram()
            if back[0x4F] != area:
                raise SystemExit(f'round {n}: walking out did not return to area {area}')
            # Mark keeps walking while LEFT is still held after the redraw; put
            # him back on the door column (screen X only, camera untouched).
            cam = ((back[0x50] + back[0x51]) << 8) | back[0x25]
            writes = {0x03D6: (d['world_x'][0] - cam + 8) & 0xFF, 0x03CB: d['row'] * 16 + 4}
            if n == 7 and d['row'] == 11:
                writes.update({0x03CB: 0xAF, 0x0330: back[0x0330] & ~2, 0x036C: 0})
            chain.fixture(f'{label}-nudge', writes,
                          f'Round {n}: Mark back onto door {d["index"]} column after walking out')
            here = enter(d, 'up')
        else:
            here = enter(d, 'warp')
        now = chain.ram()
        if is_room(d, area):
            entered = now[0x4F] == d['dest_area']
        else:
            # The camera can drift after arrival (e.g. a hit); the loader's
            # destination/arrival registers retain the actual table dispatch.
            entered = (now[0x4F] == area and now[0x6B] == d['dest_6B'] and now[0x6E] == d['dest_6E']
                       and now[0x51] == d['param_6C'] and now[0x53] == 0
                       and now[0x6F] == (d['arrival'] & 0xF0) + 4
                       and now[0x70] == ((d['arrival'] << 4) + 8) & 0xFF)
        row = dict(door=d['index'], dest_area=d['dest_area'], guardian=d['guardian'], room=d['param_6C'],
                   reached_area=now[0x4F], entered=entered)
        if not entered:
            raise SystemExit(f'round {n}: door {d["index"]} did not take Mark anywhere')
        in_room = now[0x4F] != area
        if in_room:
            row['counted'] = visit_room(d, label)
            room_checkpoint = chain.state
            if chain.ram()[0x58] == 0:
                clear_checkpoint = chain.state
        row['guardians_left'] = chain.ram()[0x58]
        results['doors'].append(row)
    if args.clear:
        if clear_checkpoint:
            chain.log.append(dict(branch=str(clear_checkpoint), purpose='Exit from a naturally cleared room checkpoint; optional encounter branches remain separate'))
            chain.state = clear_checkpoint
            in_room = True
        if chain.ram()[0x58]:
            raise SystemExit(f'round {n}: {chain.ram()[0x58]} guardians left before the exit; not forcing it')
        if not in_room:
            if not room_checkpoint:
                raise SystemExit(f'round {n}: no room checkpoint for exit setup')
            chain.log.append(dict(branch=str(room_checkpoint), purpose='Return to cleared room for round-exit case'))
            chain.state = room_checkpoint
        return_point(chain, 'exit-return-point', exit_x, exit_row,
                     f'Round {n}: walk out of the room in front of the round exit', segmented=n == 7)
        leave(chain, 'exit')
        back = chain.ram()
        cam = ((back[0x50] + back[0x51]) << 8) | back[0x25]
        chain.fixture('exit-nudge', {0x03D6: (exit_x - cam + 8) & 0xFF, 0x03CB: exit_row * 16 + 4},
                      f'Round {n}: Mark back onto the round exit column after walking out')
        r = chain.seg('exit', 900, lambda f: [f'{f} UP', f'{f + 6} -'])
        results['after_exit'] = dict(round=r['ram'][0x97] + 1, area=r['ram'][0x4F], guardians=r['ram'][0x58])
        if n < 8 and r['ram'][0x97] != n:
            raise SystemExit(f'round {n}: exit did not advance to round {n + 1}: {results["after_exit"]}')
        if n < 8:
            # One START dismisses the password, another starts the round card.
            for attempt in range(3):
                r = chain.seg(f'next-round{attempt}', 500, lambda f: [f'{f + 20} START', f'{f + 26} -'])
                if r['ram'][0x4F] == n and r['ram'][0x58] == GUARDS[n]:
                    break
            results['next_round'] = dict(round=r['ram'][0x97] + 1, area=r['ram'][0x4F], guardians=r['ram'][0x58])
            if r['ram'][0x4F] != n or r['ram'][0x58] != GUARDS[n]:
                raise SystemExit(f'round {n}: next-round initialization failed: {results["next_round"]}')
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
    ap.add_argument('--output', type=Path, help='evidence root (default: evidence/coverage/TAG)')
    ap.add_argument('--exe', type=Path, default=mp_run.EXE)
    ap.add_argument('--widescreen', choices=('16:9', '21:9', '32:9', 'fit'))
    ap.add_argument('--mods-root', type=Path, help='isolated mod catalog to validate')
    ap.add_argument('--assist', help='override developer assists (empty for none)')
    args = ap.parse_args()
    args.extra = ['--mods-root', str(args.mods_root.resolve())] if args.mods_root else []
    root = args.output.resolve() if args.output else ROOT / 'evidence' / 'coverage' / args.tag
    root.mkdir(parents=True, exist_ok=True)
    args.title_state = root / 'title-1000.cycstate'
    if not args.title_state.exists():
        r = mp_run.run(root, 'title', 1000, route=TITLE_ROUTE, assist=None, exe=args.exe, extra=args.extra)
        shutil.copyfile(r['state'],args.title_state)
    summary = [play_round(n, args, root) for n in args.rounds]
    (root / f'summary-{"-".join(map(str, args.rounds))}.json').write_text(json.dumps(summary, indent=1) + '\n', newline='\n')


if __name__ == '__main__':
    main()
