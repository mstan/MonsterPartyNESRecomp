"""A real pill pickup and flight beyond normal expiry with Endless Bert.

Only an enemy's dropped item is positioned. The game sets the transformation
flag and animation itself; neither $5E nor $54 is changed by the fixture.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import cycstate
import mp_run


def main(args):
    args.out.mkdir(parents=True, exist_ok=True)
    extra = ['--mods-root', str(args.catalog)]
    first = mp_run.start_frame(args.state)
    objects = mp_run.run(args.out, 'objects', 450, state=args.state,
                         route=f'{first} RIGHT\n{first+449} -\n', assist='life', extra=extra, exe=args.exe)
    ram = objects['ram']
    assert not ram[0x5E] & 128, 'Pickup setup must begin as Mark'
    slot = next(i for i in range(6, 9) if ram[0x300+i] < 128 and ram[0x3C0+i] & 128)
    pill = args.out / 'pill.cycstate'
    cycstate.fixture(objects['state'], pill,
        {0x30C+slot: 60, 0x330+slot: ram[0x330+slot] | 16, 0x418+slot: 0x80,
         0x42E+slot: 0x2F, 0x3CB+slot: ram[0x3CB], 0x3D6+slot: ram[0x3D6],
         0x40D+slot: ram[0x40D], 0x3C0+slot: 0x80, 0x3EC+slot: 8, 0x3F7+slot: 8},
        'Assisted enemy pill drop. Actual collision invokes 4:90D2 and 4:887D; no transformation/timer writes.')
    pickup = mp_run.run(args.out, 'pickup', 500, state=pill, assist='life', extra=extra, exe=args.exe)
    assert pickup['ram'][0x5E] & 128 and pickup['ram'][0x54] == 0
    first = mp_run.start_frame(pickup['state'])
    route = f'{first} UP B\n{first+100} RIGHT B\n{first+250} LEFT B\n{first+500} -\n'
    for interp in (False, True):
        result = mp_run.run(args.out, 'flight-interp' if interp else 'flight', 3600,
                           state=pickup['state'], route=route, assist='life', extra=extra,
                           exe=args.exe, interp=interp)
        assert result['ram'][0x5E] & 128 and result['ram'][0x54] == 0
    checks = dict(real_pill_pickup=True, transformed_beyond_normal_expiry=True)
    for ext in ('.hash', '.png', '.cycstate'):
        checks[ext] = (args.out / ('flight'+ext)).read_bytes() == (args.out / ('flight-interp'+ext)).read_bytes()
    (args.out / 'results.json').write_text(json.dumps(checks, indent=2)+'\n', newline='\n')
    assert all(checks.values()), checks
    print(json.dumps(checks), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    main(parser.parse_args())
