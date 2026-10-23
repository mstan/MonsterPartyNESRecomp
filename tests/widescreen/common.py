"""Shared helpers for the Monster Party widescreen regressions (hidden, headless).

Every run is a native process with SDL's dummy drivers and no window; evidence
stays beneath wide-evidence/ (gitignored). Rounds start from the per-round
checkpoints evidence/rounds/round{N}-start.cycstate (frame 1400, in-level).
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import cycstate  # noqa: E402

EXE = REPO / 'build-wide' / 'MonsterPartyRecomp.exe'
ROM = REPO / 'monsterparty.nes'
ROUNDS = REPO / 'evidence' / 'rounds'
PACKAGE = 'monster-party.enhancement.widescreen'
START = 1400
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', LNG_TEST_HIDDEN='1',
           NESRECOMP_NO_LAUNCHER='1')
WIDTHS = {'16:9': 426, '21:9': 560, '32:9': 854}


def hidden():
    if not hasattr(subprocess, 'STARTUPINFO'):
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return dict(startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)


def route(frames, start=START, back=0):
    """Walk right with periodic jumps and swings for `frames` frames, then
    walk left for the last `back` frames (both scroll directions)."""
    lines = []
    end = start + frames
    for f in range(start, end - back, 48):
        lines += [f'{f} RIGHT', f'{f + 20} RIGHT+A', f'{f + 34} RIGHT+B', f'{f + 40} RIGHT']
    if back:
        for f in range(end - back, end, 48):
            lines += [f'{f} LEFT', f'{f + 20} LEFT+A', f'{f + 34} LEFT+B', f'{f + 40} LEFT']
    return '\n'.join(lines) + '\n'


def checkpoint(n):
    return ROUNDS / f'round{n}-start.cycstate'


def run(out, name, frames, state, route_text='', args=(), exe=EXE, saves=(), present=True, report=True):
    """Run `frames` frames after the state's frame; returns paths and parsed report rows."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / name
    end = START + frames
    rpath = stem.with_suffix('.route.txt')
    rpath.write_text(route_text, newline='\n')
    cmd = [str(exe), str(ROM), '--no-save', '--frames', str(end), '--load-state', str(Path(state).resolve()),
           '--hash-out', str(stem.with_suffix('.hash')), '--screenshot', str(stem.with_suffix('.native.png')),
           '--save-state', f'{end - 1}:{stem.with_suffix(".cycstate")}', '--mp-assist', 'life']
    if route_text:
        cmd += ['--input', str(rpath)]
    if present:
        cmd += ['--present-out', str(stem.with_suffix('.present.png'))]
    if report:
        cmd += ['--widescreen-report', str(stem.with_suffix('.jsonl'))]
    for frame, path in saves:
        cmd += ['--save-state', f'{frame}:{path}']
    cmd += [str(a) for a in args]
    stem.with_suffix('.command.json').write_text(json.dumps(cmd, indent=1) + '\n', newline='\n')
    with stem.with_suffix('.log').open('w') as log:
        proc = subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT, env=ENV, timeout=1800, **hidden())
    text = stem.with_suffix('.log').read_text(errors='replace')
    if proc.returncode:
        raise AssertionError(f'{name}: exit {proc.returncode}\n{text[-2000:]}')
    rows = []
    if report and stem.with_suffix('.jsonl').exists():
        rows = [json.loads(s) for s in stem.with_suffix('.jsonl').read_text().splitlines() if s.strip()]
    return dict(name=name, stem=stem, hash=stem.with_suffix('.hash'), state=stem.with_suffix('.cycstate'),
                native=stem.with_suffix('.native.png'), present=stem.with_suffix('.present.png'), rows=rows, log=text)


def same_file(a, b):
    return Path(a).read_bytes() == Path(b).read_bytes()


def chunks_without(path, tags=(b'MOD ',)):
    """A state's chunks minus the given tags (mod records), for machine-only comparison."""
    data = Path(path).read_bytes()
    return [(b'HEAD', data[:32])] + [(tag, data[at:at + n]) for tag, at, n in cycstate.chunks(data) if tag not in tags]


def png_size(path):
    data = Path(path).read_bytes()
    return struct.unpack('>II', data[16:24])
