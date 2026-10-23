"""Content keys for game.toml [[mod_function_hook]] sites, from the cartridge ROM.

  python tools/hook_keys.py monsterparty.nes                 # print keys of declared sites
  python tools/hook_keys.py monsterparty.nes --key 5:8D22    # key for a new site (length 8)
  python tools/hook_keys.py monsterparty.nes --check         # fail when game.toml disagrees

A hook site is keyed on the code at its address (runner/cyc/cyc_hooks.h): the
CRC-32 of `length` bytes there, so the repository holds no bytes of the game.
Banks 0-6 switch into $8000-$BFFF; bank 7 is fixed at $C000-$FFFF.
"""
import argparse
import sys
import tomllib
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def banks(rom):
    raw = Path(rom).read_bytes()
    prg = raw[16:16 + raw[4] * 16384]
    return [prg[i * 16384:(i + 1) * 16384] for i in range(raw[4])]


def holders(b, addr, length, crc):
    out = []
    for n, data in enumerate(b):
        org = 0xC000 if n == len(b) - 1 else 0x8000
        if org <= addr and addr + length <= org + 0x4000 and zlib.crc32(data[addr - org:addr - org + length]) == crc:
            out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rom', type=Path)
    ap.add_argument('--key', help='BANK:ADDR (hex) to key a new site')
    ap.add_argument('--length', type=int, default=8)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    b = banks(a.rom)
    if a.key:
        bank, addr = a.key.split(':')
        bank, addr = int(bank), int(addr, 16)
        org = 0xC000 if bank == len(b) - 1 else 0x8000
        crc = zlib.crc32(b[bank][addr - org:addr - org + a.length])
        print(f'addr = 0x{addr:04X}\nlength = {a.length}\ncrc32 = 0x{crc:08X}  # banks holding it: {holders(b, addr, a.length, crc)}')
        return 0
    game = tomllib.loads((ROOT / 'game.toml').read_text(encoding='utf-8'))
    bad = 0
    for hook in game.get('mod_function_hook', []):
        found = holders(b, hook['addr'], hook.get('length', 8), hook.get('crc32', -1))
        print(f"{hook.get('id', '(no id)')}: ${hook['addr']:04X} banks {found or 'NONE'}")
        bad += not found
    if a.check and bad:
        print(f'{bad} site(s) match no bank', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
