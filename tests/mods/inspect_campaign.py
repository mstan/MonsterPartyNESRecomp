"""Inspect retained campaign pixels: all doors, centered HUD and room content."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import cycstate
sys.path.insert(0, str(ROOT / 'nesrecomp/tools/cyc'))
from test_cyc_hdpack import png_read


def main(args):
    results = []
    rounds = {}
    for root in args.roots:
        for file in sorted(root.glob('round*/chain.json')):
            chain = json.loads(file.read_text())
            result = chain['results']
            assert result['round'] not in rounds, 'Provide each completed round once'
            rounds[result['round']] = result
            assert all(door['entered'] for door in result['doors'])
            for segment in chain['segments']:
                if 'segment' not in segment:
                    continue
                base = file.parent / segment['segment']
                picture, present, state = [base.with_suffix(ext) for ext in ('.png', '.present.png', '.cycstate')]
                w, h, native = png_read(picture)
                pw, ph, wide = png_read(present)
                assert (w, h, pw, ph) == (256, 240, 854, 240)
                ram = cycstate.ram(state.read_bytes())
                hud = all(wide[y][299*3:(299+256)*3] == native[y] for y in range(192, 240))
                room = bool(ram[0x52] & 128) or not ram[0x32E]
                # Border sprites can legitimately extend across the original
                # eight-pixel clipping boundary. The inner room stays native.
                centered = not room or all(wide[y][307*3:547*3] == native[y][8*3:248*3] for y in range(192))
                results.append(dict(round=result['round'], segment=segment['segment'], hud=hud,
                                    room=room, centered=centered))
                assert hud and centered, results[-1]
    assert set(rounds) == set(range(1, 9)), sorted(rounds)
    output = dict(rounds=sorted(rounds), doors=sum(len(r['doors']) for r in rounds.values()),
                  guardian_flags_and_round_exits=True, images=len(results),
                  room_images=sum(row['room'] for row in results), checks=results)
    args.out.write_text(json.dumps(output, indent=1)+'\n', newline='\n')
    print(json.dumps({key: value for key, value in output.items() if key != 'checks'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', type=Path, nargs='+', required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
