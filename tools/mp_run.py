"""Run one deterministic headless Monster Party segment and keep its evidence.

A segment starts from power-on or a save state, applies an input route (absolute
frame numbers, cyc_host.c format), optional developer assists, and ends with a
save state. Native runs harvest --miss-log/--capture-log; --interp-only runs are
the parity reference. Nothing here opens a window.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycstate  # noqa: E402

EXE = ROOT / 'build' / 'MonsterPartyRecomp.exe'
ROM = ROOT / 'monsterparty.nes'
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', LNG_TEST_HIDDEN='1', NESRECOMP_NO_LAUNCHER='1')


def start_frame(state):
    """The frame a loaded state continues at (cyc_host: 'continuing at frame N')."""
    if not state:
        return 0
    data = Path(state).read_bytes()
    for tag, at, length in cycstate.chunks(data):
        if tag == b'HOST':
            return int.from_bytes(data[at + 8:at + 16], 'little')  # HostState.next_frame
    raise ValueError('state has no HOST chunk')


def run(out, name, frames, state=None, route='', assist=None, pokes=(), shots=0, interp=False,
        harvest=True, extra=(), exe=EXE, rom=ROM, timeout=1800):
    """frames: how many frames to run from the state. Returns a result dict."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    first = start_frame(state)
    end = first + frames
    stem = out / name
    route_path = stem.with_suffix('.route.txt')
    route_path.write_text(route if route.endswith('\n') or not route else route + '\n')
    cmd = [str(exe), str(rom), '--no-save', '--frames', str(end),
           '--hash-out', str(stem.with_suffix('.hash')), '--screenshot', str(stem.with_suffix('.png')),
           '--save-state', f'{end - 1}:{stem.with_suffix(".cycstate")}']
    if route:
        cmd += ['--input', str(route_path)]
    if state:
        cmd += ['--load-state', str(Path(state).resolve())]
    if shots:
        cmd += ['--shot-every', str(shots)]
    if assist:
        cmd += ['--mp-assist', assist]
    for p in pokes:
        cmd += ['--mp-poke', p]
    if interp:
        cmd += ['--interp-only']
    elif harvest:
        cmd += ['--miss-log', str(out / 'misses.txt'), '--capture-log', str(out / 'captures.txt')]
    cmd += list(extra)
    stem.with_suffix('.command.json').write_text(json.dumps(cmd, indent=2) + '\n')
    log = stem.with_suffix('.log')
    with log.open('w') as f:
        proc = subprocess.run(cmd, cwd=out, stdout=f, stderr=subprocess.STDOUT, env=ENV, timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    text = log.read_text(errors='replace')
    if proc.returncode:
        raise RuntimeError(f'{name}: exit {proc.returncode}; see {log}')
    if '$2000-$5FFF' in text:
        raise RuntimeError(f'{name}: unmapped execution; see {log}')
    data = stem.with_suffix('.cycstate').read_bytes()
    m = re.search(r'cycles=(\d+) native_cycles=(\d+)', text)
    ram = cycstate.ram(data)
    return dict(name=name, state=str(stem.with_suffix('.cycstate')), png=str(stem.with_suffix('.png')),
                first=first, end=end, ram=ram, cycles=int(m[1]) if m else None,
                native=int(m[2]) if m else None, interp_rom=_interp(text, 'ROM'), log=str(log))


def _interp(text, kind):
    m = re.search(kind + r' (\d+) \(', text)
    return int(m[1]) if m else None


def show(r, *addrs):
    ram = r['ram']
    vals = ' '.join(f'{a:03X}={ram[a]:02X}' for a in addrs)
    print(f"{r['name']}: frames {r['first']}-{r['end']} native {r['native']}/{r['cycles']} interpROM {r['interp_rom']} | {vals}")
