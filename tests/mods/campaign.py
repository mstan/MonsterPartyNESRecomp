"""Restoration content audit using the actual patched tables, held in memory.

The normal campaign performs real door entries, landed hits and round exits.
Position/life fixtures are assisted setup; success flags are never forced.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/coverage'))
import campaign as coverage
import ending
sys.path.insert(0, str(ROOT / 'tests/mods'))
from validate import catalog


def restored_banks():
    image = bytearray((ROOT / 'monsterparty.nes').read_bytes())
    patch = (ROOT / 'mods/preloaded/packages/monster-party.content.prototype-restoration/1.0.0/restoration.ips').read_bytes()
    assert zlib.crc32(image[16:]) == 0x02B9E7C2
    at = 5
    while patch[at:at+3] != b'EOF':
        offset = int.from_bytes(patch[at:at+3], 'big')
        count = int.from_bytes(patch[at+3:at+5], 'big')
        at += 5
        if count:
            image[offset:offset+count] = patch[at:at+count]
            at += count
        else:
            count = int.from_bytes(patch[at:at+2], 'big')
            image[offset:offset+count] = bytes([patch[at+2]]) * count
            at += 3
    assert zlib.crc32(image[16:]) == 0x71DB905B
    return [bytes(image[16+i*16384:16+(i+1)*16384]) for i in range(8)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rounds', nargs='+', type=int, default=list(range(1, 9)))
    parser.add_argument('--parity', action='store_true')
    cli = parser.parse_args()
    cli.out.mkdir(parents=True, exist_ok=True)
    cat = catalog(cli.out / 'catalog', {'invincibility': {}, 'one-hit': {'targets': 'guardians'}}, True, True)
    banks = restored_banks()
    coverage.mp_map.load = lambda rom: banks
    coverage.mp_doors.load = lambda rom: banks
    args = SimpleNamespace(exe=cli.exe, parity=cli.parity, clear=True, doors=None,
                           fight_frames=1200, fight_tries=4, widescreen='32:9', assist='life',
                           extra=['--mods-root', str(cat)], title_state=cli.out / 'title.cycstate')
    if not args.title_state.exists():
        result = coverage.mp_run.run(cli.out, 'title', 1000, route=coverage.TITLE_ROUTE,
                                     exe=args.exe, extra=args.extra)
        assert Path(result['state']) == args.title_state
    results = [coverage.play_round(n, args, cli.out) for n in cli.rounds]
    (cli.out / 'summary.json').write_text(json.dumps(results, indent=2) + '\n', newline='\n')
    if 8 in cli.rounds:
        rows = json.loads((cli.out / 'round8/segments.json').read_text())
        last = next(row['segment'] for row in reversed(rows) if row.get('segment', '').endswith('-exit'))
        args.state = cli.out / 'round8' / f'{last}.cycstate'
        args.output = cli.out / 'ending'
        args.sections = 20
        ending.finish(args)


if __name__ == '__main__':
    main()
