"""Hidden AppImage launcher, native picker handoff and user-data preservation."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    stub = root/'picker'
    stub.mkdir()
    zenity = stub/'zenity'
    zenity.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys
pathlib.Path(os.environ['PICKER_RECORD']).write_text(json.dumps(dict(argv=sys.argv,library_path=os.environ.get('LD_LIBRARY_PATH',''))))
print(os.environ['PICKER_ROM'])
''', newline='\n')
    zenity.chmod(0o755)
    env = dict(os.environ, APPIMAGE_EXTRACT_AND_RUN='1', SDL_AUDIODRIVER='dummy',
               SDL_VIDEODRIVER='x11', LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='2',
               MESA_SHADER_CACHE_DISABLE='true', LNG_TEST_HIDDEN='1',
               XDG_DATA_HOME=str(root/'data'), XDG_CONFIG_HOME=str(root/'config'),
               XDG_CACHE_HOME=str(root/'cache'), TMPDIR=str(root/'tmp'),
               PATH=str(stub)+':'+os.environ['PATH'], PICKER_ROM=str(args.rom.resolve()),
               PICKER_RECORD=str(root/'picker.json'))
    env.pop('NESRECOMP_NO_LAUNCHER', None)
    env.pop('LD_LIBRARY_PATH', None)
    (root/'tmp').mkdir()
    def run(name, arguments, script=None):
        current = dict(env)
        if script:
            current['LNG_SCRIPT'] = script
        else:
            current['NESRECOMP_NO_LAUNCHER'] = '1'
            current['SDL_VIDEODRIVER'] = 'dummy'
        cmd = [str(args.appimage.resolve())] + arguments
        (root/(name+'.command.json')).write_text(json.dumps(cmd, indent=1)+'\n', newline='\n')
        with (root/(name+'.log')).open('w', newline='\n') as log:
            subprocess.run(cmd, env=current, cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
    run('picker', ['--hidden', '--no-save'],
        f'size:1100x880;wait:12;shot:{root}/first-run.png;click:224,654;wait:40;shot:{root}/verified.png;click:1020,48;wait:12;shot:{root}/mods.png;quit')
    data = root/'data/MonsterParty'
    picker = json.loads((root/'picker.json').read_text())
    assert picker['library_path'] == ''
    assert '--file-selection' in picker['argv']
    assert (data/'rom.cfg').read_text().strip() == str(args.rom.resolve())
    config = (data/'config.ini').read_text()
    assert 'Fullscreen = 0' in config and 'Enabled = 1' in config and 'Volume = 100' in config
    (data/'config.ini').write_text(config.replace('Volume = 100', 'Volume = 37'), newline='\n')
    (data/'saves').mkdir(exist_ok=True)
    (data/'saves/preservation.sav').write_bytes(b'player-save-sentinel')
    (data/'mods/user-preservation.txt').write_text('user-installed content\n', newline='\n')
    (data/'mods/state.toml').write_text('''[[package]]
id = "monster-party.enhancement.widescreen"
version = "1.0.0"
[[feature]]
package_id = "monster-party.enhancement.widescreen"
id = "widescreen"
enabled = true
[feature.values]
aspect = "fit"
''', newline='\n')
    preserved = {p: (data/p).read_bytes() for p in ('config.ini', 'rom.cfg', 'saves/preservation.sav', 'mods/state.toml', 'mods/user-preservation.txt')}
    (data/'.payload-id').write_text('force-test-refresh\n', newline='\n')
    run('refresh', [str(args.rom.resolve()), '--frames', '1', '--no-save'])
    assert all((data/p).read_bytes() == contents for p, contents in preserved.items())
    assert (data/'.payload-id').read_text().strip() != 'force-test-refresh'
    assert not (data/'lib/libstdc++.so.6').exists()
    run('reopen', ['--hidden', '--no-save'], f'size:1100x880;wait:12;click:1020,48;wait:12;shot:{root}/reopened-mods.png;quit')
    assert (data/'mods/state.toml').read_bytes() == preserved['mods/state.toml']
    result = dict(passed=True, native_picker_handoff=True, host_picker_environment=True,
                  windowed_audio_defaults=True, refreshed_user_data_preserved=list(preserved),
                  settings_reopened=True, no_bundled_old_cpp_runtime=True)
    (root/'results.json').write_text(json.dumps(result, indent=1)+'\n', newline='\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--appimage', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
