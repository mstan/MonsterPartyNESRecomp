"""Drive the real F7/F8 interfaces in an isolated, silent SDL window.

python tests/state_ui.py --exe PATH --out PATH [--interp] [--widescreen]
No player files are used. Screenshots and machine snapshots stay in --out.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class Game:
    def __init__(self, exe, out, extra):
        self.out = out.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        app = self.out / 'app'
        app.mkdir(exist_ok=True)
        for source in [exe, *exe.parent.glob('*.dll')]:
            shutil.copy2(source, app / source.name)
        for name in ('assets', 'mods'):
            if (exe.parent / name).is_dir():
                shutil.copytree(exe.parent / name, app / name, dirs_exist_ok=True)
        self.app = app
        config = self.out / 'config.ini'
        # Obsolete quick-slot bindings must not shadow the new defaults.
        config.write_text('[Keyboard.Shortcuts]\nsave_state=F8\nload_state=F9\n'
                          '[Rewind]\nEnabled=1\nDepth=50\nInterval=4\n', newline='\n')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        self.log = (self.out / 'runtime.log').open('w', encoding='utf-8', newline='\n')
        self.process = subprocess.Popen(
            [str(app / exe.name), str(ROOT / 'monsterparty.nes'), '--config', str(config),
             '--tcp', str(port), '--hidden', '--no-save', *extra], cwd=self.out,
            env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                     NESRECOMP_NO_LAUNCHER='1'), stdout=self.log, stderr=subprocess.STDOUT,
            creationflags=NO_WINDOW)
        self.sock = None
        self.buffer = b''
        self.serial = 0
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                self.sock = socket.create_connection(('127.0.0.1', port), timeout=5)
                return
            except OSError:
                if self.process.poll() is not None:
                    raise RuntimeError(f'Game exited {self.process.returncode}: {self.out / "runtime.log"}')
                time.sleep(.1)
        raise TimeoutError('No game TCP server')

    def cmd(self, command, **fields):
        self.serial += 1
        request = dict(cmd=command, id=self.serial, **fields)
        self.sock.sendall((json.dumps(request) + '\n').encode())
        while b'\n' not in self.buffer:
            data = self.sock.recv(65536)
            assert data, 'Game disconnected'
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        reply = json.loads(line)
        assert reply.get('ok') and reply['id'] == self.serial, reply
        return reply

    def state(self):
        return self.cmd('state')

    def until(self, condition, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = self.state()
            if condition(state):
                return state
            time.sleep(.02)
        raise AssertionError(f'Timed out: {state}')

    def key(self, name, frames=3):
        self.cmd('key', name=name, frames=frames)
        time.sleep((frames + 3) / 60)

    def pad(self, buttons, frames=3):
        self.cmd('pad', buttons=buttons, frames=frames)
        time.sleep((frames + 3) / 60)

    def panel(self, name):
        return self.until(lambda state: state['state_panel'] == name)

    def snapshot(self, name):
        path = self.out / f'{name}.cycstate'
        self.cmd('save_state', path=str(path))
        return path.read_bytes()

    def picture(self, name, layer='picture'):
        path = self.out / f'{name}.png'
        self.cmd('screenshot', layer=layer, path=str(path))
        return path.read_bytes()

    def close(self):
        try:
            if self.sock and self.process.poll() is None:
                self.cmd('quit')
                self.process.wait(20)
                assert self.process.returncode == 0
        finally:
            if self.sock:
                self.sock.close()
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.log.close()


def run(args):
    extra = ['--interp-only'] if args.interp else []
    if args.widescreen:
        extra += ['--widescreen', '32:9']
    game = Game(args.exe.resolve(), args.out, extra)
    results = {}
    try:
        game.until(lambda s: s['frame'] > 100 and s['rewind_count'] > 10)
        # Load an observed stage fixture through the live window, not the CLI's
        # headless --load-state path. A rejected older fixture is a test failure,
        # never a requirement to add a backward-compatibility converter.
        game.cmd('load_state', path=str(ROOT / 'evidence/rounds/round1-start.cycstate'))
        start = game.state()['frame']
        game.until(lambda s: s['frame'] > start + 100)
        game.key('F7')
        paused = game.panel('states')
        time.sleep(.2)
        assert game.state()['frame'] == paused['frame'], 'State browser failed to pause'
        before = game.snapshot('before-save')
        picture = game.picture('before-save')
        game.key('S')
        slot = game.app / 'saves/monsterparty.slot01.cycstate'
        assert slot.read_bytes() == before, 'UI save differs from the whole-machine snapshot'
        assert slot.with_suffix('.cycstate.thumb').stat().st_size == 20 + 192 * 108 * 4
        game.picture('states-ui', 'ui')
        results['save_pauses_and_preserves_machine'] = True
        # Invalid state input must leave the paused machine intact.
        game.key('Right')
        assert game.state()['state_slot'] == 2
        bad = game.app / 'saves/monsterparty.slot02.cycstate'
        bad.write_bytes(b'not a valid snapshot')
        game.key('Return')
        assert game.state()['state_panel'] == 'states'
        assert game.snapshot('after-invalid') == before, 'Rejected load changed machine state'
        assert game.picture('after-invalid') == picture
        results['invalid_load_is_transactional'] = True
        # A gamepad-created slot survives restarting the program.
        game.pad('dpright')
        game.pad('x')
        third = game.app / 'saves/monsterparty.slot03.cycstate'
        assert third.read_bytes() == before
        results['controller_slot_save'] = True
        for _ in range(10):
            game.key('Right')
        assert game.state()['state_slot'] == 12
        game.key('S')
        assert (game.app / 'saves/monsterparty.slot12.cycstate').read_bytes() == before
        game.picture('states-last-slot-ui', 'ui')
        for _ in range(10):
            game.key('Left')
        assert game.state()['state_slot'] == 2
        results['all_twelve_slots_reachable'] = True
        game.key('Escape')
        game.panel('closed')
        game.until(lambda s: s['frame'] > paused['frame'] + 60)
        # F7 over the ordinary menu must replace it; closing cannot strand a pause.
        game.key('Escape')
        game.until(lambda s: s['menu_open'])
        game.key('F7')
        game.panel('states')
        game.key('Escape')
        closed = game.panel('closed')
        assert not closed['menu_open'], 'Ordinary menu remained behind the browser'
        game.until(lambda s: s['frame'] > closed['frame'] + 10)
        results['modal_replaces_runtime_menu'] = True
        # Controller shortcut and controller save/load. Slot one was saved above.
        game.pad('back+leftstick')
        game.panel('states')
        game.pad('dpleft')
        assert game.state()['state_slot'] == 1
        original_y = game.cmd('read_ram', addr=0x03CB, len=1)['hex']
        game.pad('a', 18)
        loaded = game.panel('closed')
        assert paused['frame'] <= loaded['frame'] < paused['frame'] + 40, loaded
        assert game.cmd('read_ram', addr=0x03CB, len=1)['hex'] == original_y, 'Load button leaked into a jump'
        game.until(lambda s: s['frame'] > paused['frame'] + 80)
        results['controller_state_load'] = True
        game.key('F8')
        original = game.panel('rewind')
        assert original['menu_open'] and original['rewind_count'] > 10
        current_blob = game.snapshot('before-rewind')
        current_picture = game.picture('before-rewind')
        for _ in range(8):
            game.key('Left')
        earlier = game.state()
        assert earlier['rewind_frame'] < original['rewind_frame']
        game.picture('rewind-ui', 'ui')
        assert game.snapshot('rewind-preview') == current_blob, 'Scrubbing changed the guest'
        assert game.picture('rewind-preview') == current_picture
        game.key('Escape')
        game.panel('closed')
        results['rewind_preview_is_non_destructive'] = True
        game.pad('back+rightstick')
        original = game.panel('rewind')
        for _ in range(8):
            game.pad('dpleft')
        selected = game.state()['rewind_frame']
        game.pad('a')
        restored = game.panel('closed')
        assert selected <= restored['frame'] < selected + 20
        assert restored['rewind_count'] < original['rewind_count'], (original, restored)
        game.key('F8')
        branched = game.panel('rewind')
        assert branched['rewind_frame'] < original['rewind_frame'], 'Abandoned future survived'
        game.key('Escape')
        game.panel('closed')
        results['rewind_commit_trims_future'] = True
        results['old_shortcuts_do_not_shadow_f7_f8'] = True
        results['final_state'] = game.state()
    finally:
        game.close()
        (args.out / 'results.json').write_text(json.dumps(results, indent=2) + '\n', newline='\n')
    game = Game(args.exe.resolve(), args.out, extra)
    try:
        game.until(lambda s: s['frame'] > 60)
        game.key('F7')
        game.panel('states')
        game.key('Right')
        game.key('Right')
        game.key('Return')
        restored = game.panel('closed')
        assert paused['frame'] <= restored['frame'] < paused['frame'] + 20
        results['state_survives_restart'] = True
    finally:
        game.close()
        (args.out / 'results.json').write_text(json.dumps(results, indent=2) + '\n', newline='\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--interp', action='store_true')
    parser.add_argument('--widescreen', action='store_true')
    run(parser.parse_args())
