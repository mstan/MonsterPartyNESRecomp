"""Exercise the actual AppImage, including cross-platform gameplay comparisons."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mp_run
sys.path.insert(0, str(ROOT / 'tests/widescreen'))
from validate import route


def main(args):
    mp_run.ENV['APPIMAGE_EXTRACT_AND_RUN'] = '1'
    records = []
    args.output.mkdir(parents=True, exist_ok=True)
    for n in range(1, 9):
        state = ROOT / f'evidence/rounds/round{n}-start.cycstate'
        first = mp_run.start_frame(state)
        middle = args.output / f'round{n}-middle.cycstate'
        text = route(first, 120)

        def run(name, checkpoint=state, frames=120, inputs=text, interp=False, save=False):
            extra = ['--widescreen', '32:9', '--present-out', str(args.output / (name + '.present.png'))]
            if save:
                extra += ['--save-state', f'{first+59}:{middle}']
            return mp_run.run(args.output, name, frames, state=checkpoint, route=inputs,
                              assist='life', exe=args.appimage, interp=interp, harvest=False,
                              extra=extra, timeout=120)

        run(f'round{n}', save=True)
        run(f'round{n}-interp', interp=True)
        suffix = [line for line in text.splitlines() if int(line.split()[0]) >= first+60]
        prior = [line for line in text.splitlines() if int(line.split()[0]) < first+60][-1]
        suffix.insert(0, f'{first+60} {prior.split(" ", 1)[1]}')
        run(f'round{n}-reload', checkpoint=middle, frames=60, inputs='\n'.join(suffix)+'\n')
        def data(name, ext):
            return (args.output / (name+ext)).read_bytes()
        checks = {}
        for ext in ('.hash', '.png', '.present.png', '.cycstate'):
            checks['interpreter'+ext] = data(f'round{n}', ext) == data(f'round{n}-interp', ext)
        for ext in ('.hash', '.png', '.present.png'):
            actual = data(f'round{n}', ext)
            expected = (args.windows_evidence/f'round{n}'/('32-9'+ext)).read_bytes()
            # Text-mode C stdio emits CRLF on Windows and LF on Linux.
            checks['windows'+ext] = actual.splitlines() == expected.splitlines() if ext == '.hash' else actual == expected
        for ext in ('.png', '.present.png', '.cycstate'):
            checks['reload'+ext] = data(f'round{n}', ext) == data(f'round{n}-reload', ext)
        checks['reload.hash'] = data(f'round{n}', '.hash').splitlines()[-60:] == data(f'round{n}-reload', '.hash').splitlines()
        records.append(dict(case=f'round{n}', checks=checks, passed=all(checks.values())))
        (args.output/'results.json').write_text(json.dumps(records, indent=1)+'\n', newline='\n')
        print(n, checks, flush=True)
        assert all(checks.values()), n


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--appimage', type=Path, required=True)
    parser.add_argument('--windows-evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
