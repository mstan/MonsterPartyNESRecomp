"""Stage the shared player-facing files; never copy a development tree wholesale."""
import argparse
from pathlib import Path
import shutil
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def stage(build, output, version):
    output.mkdir(parents=True, exist_ok=True)
    if any((output / p).exists() for p in ('config.ini', 'rom.cfg', 'saves')):
        raise RuntimeError('Refusing to stage over player data')
    shutil.copytree(build / 'assets', output / 'assets', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'mods/preloaded/packages', output / 'mods/packages', dirs_exist_ok=True)
    notices = {
        'MonsterParty-LICENSE.md': ROOT / 'LICENSE.md',
        'NESRecomp-LICENSE.txt': ROOT / 'nesrecomp/LICENSE',
        'SDL2-COPYING.txt': ROOT / 'nesrecomp/runner/external/SDL2/COPYING.txt',
        'ImGui-LICENSE.txt': ROOT / 'recomp-ui/src/third_party/imgui/LICENSE.txt',
        'recomp-ui-LICENSE.txt': ROOT / 'recomp-ui/LICENSE',
        'recomp-net-LICENSE.txt': ROOT / 'nesrecomp/lib/recomp-net/LICENSE',
        'rbengine-LICENSE.txt': ROOT / 'nesrecomp/lib/retcomm-rbengine/LICENSE',
        'Fonts-NOTICE.md': ROOT / 'recomp-ui/assets/common/fonts/NOTICE.md',
        'Images-NOTICE.md': ROOT / 'recomp-ui/assets/common/img/NOTICE.md',
        'OFL-1.1.txt': ROOT / 'assets/licenses/OFL-1.1.txt',
        'Artwork-SOURCE.txt': ROOT / 'assets/SOURCE.txt',
        'Prototype-Restoration-NOTICE.txt': ROOT / 'mods/preloaded/packages/monster-party.content.prototype-restoration/1.0.0/NOTICE.txt',
        'Cheats-NOTICE.txt': ROOT / 'mods/preloaded/packages/monster-party.cheats.game-genie/1.0.0/NOTICE.txt',
    }
    (output / 'licenses').mkdir(exist_ok=True)
    for name, source in notices.items():
        shutil.copyfile(source, output / 'licenses' / name)
    text = (ROOT / 'docs/PLAYING.txt.in').read_text(encoding='utf-8').replace('@VERSION@', version)
    (output / 'README.txt').write_text(text, encoding='utf-8', newline='\n')
    forbidden = {'.nes', '.fds', '.sav', '.srm', '.cycstate', '.state', '.log', '.dmp', '.ram', '.route'}
    for p in output.rglob('*'):
        if p.is_file() and (p.suffix.lower() in forbidden or p.name in
                           {'config.ini', 'rom.cfg', 'state.toml', 'keybinds.ini', 'debug.ini'} or
                           any(s in str(p) for s in ('psx.enhancement.cd-speed', 'psx.enhancement.fast-loading'))):
            raise RuntimeError(f'Forbidden release file: {p}')
    manifest = output / 'mods/packages/monster-party.enhancement.widescreen/1.0.0/manifest.toml'
    assert [o['id'] for o in tomllib.loads(manifest.read_text(encoding='utf-8'))['option']] == ['aspect']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', default='0.1.2')
    args = parser.parse_args()
    stage(args.build, args.output, args.version)
