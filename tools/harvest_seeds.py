"""Append observed, previously absent ROM instruction starts to cyc_seeds.txt.

Inputs are --miss-log files written by native runs (lines `4k:BB:AAAA count`).
Only coordinates the interpreter actually executed are added; RAM comment lines
are ignored (code in RAM is covered by --capture-log, not seeds).
"""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r'4k:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{4}\s+\d+')


def harvest(misses, label, seeds=ROOT / 'cyc_seeds.txt'):
    old = seeds.read_text()
    have = {l.split()[0].upper() for l in old.splitlines() if l.startswith('4k:')}
    added = []
    for path in misses:
        for line in Path(path).read_text().splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            if not LINE.fullmatch(line.strip()):
                raise ValueError(f'{path}: unrecognized coordinate {line!r}')
            key = line.split()[0].upper()
            if key not in have:
                have.add(key)
                added.append(line.strip())
    if added:
        seeds.write_text(old.rstrip('\n') + f'\n\n# {label}\n' + '\n'.join(added) + '\n', newline='\n')
    return added


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--label', required=True, help='comment naming the route(s) observed')
    ap.add_argument('misses', nargs='+', type=Path)
    a = ap.parse_args()
    print(f'added {len(harvest(a.misses, a.label))} observed starts')
