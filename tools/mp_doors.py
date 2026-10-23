"""Decode Monster Party's door tables (bank 2) as the fixed-bank door code reads them.

Verified against the original code (USA):
  7:D432  Y = $4F*2; 7:D9FD loads ($7B)=$98AE[Y], ($7D)=$9A26[Y], ($7F)=$9B8E[Y]
  7:DA26  ($7B): (row, key) pairs, $FF-terminated; row = Mark Y >> 4 and key
          is 7:DA42's rotate of (world X & $F0, page + $51)
  7:D968  ($7D) byte 0 = destination area ($6A; $FF returns to the saved
          $75-$78 area/camera), byte 1 packs $6E/$6B
  7:D99A  ($7F) byte 0 = $52; bit 7 names a guardian (X = bits 4-6, defeated
          when $59+X bit 7 is set), low nibble = $6C; byte 1 = arrival
          ($6F/$70) or $FF to restore the saved Mark position
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dis6502 import load  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def rol(a, c):
    return ((a << 1) | c) & 0xFF, a >> 7


def door_key(world_x, page_offset=0):
    """7:DA42 for a world X (page*256+pixel) with $51 = page_offset; returns the key byte."""
    lo, page = world_x & 0xFF, ((world_x >> 8) + page_offset) & 0xFF
    a = (lo & 0xF0)
    a, c = (a << 1) & 0xFF, a >> 7          # ASL
    a |= page                                 # ORA $18
    for _ in range(4):                        # ROL x4
        a, c = rol(a, c)
    return a


def world_x_for_key(key, page_offset=0):
    """All 16-pixel columns (world X) whose 7:DA42 key equals key."""
    return [x for x in range(0, 0x1000, 16) if door_key(x, page_offset) == key]


def decode_dst(b1):
    a, c = (b1 << 1) & 0xFF, b1 >> 7          # ASL
    a, c = rol(a, c)
    a, c = rol(a, c)
    a, c = rol(a, c)
    x = a
    r6e = a & 0xF0
    a, c = rol(x, c)
    r6b = a & 0x0F
    return r6e, r6b


def areas(rom=ROOT / 'monsterparty.nes'):
    b = load(rom)[2]
    w = lambda a: b[a - 0x8000] | b[a - 0x7FFF] << 8
    out = []
    for area in range(16):
        pos, dst, flg = w(0x98AE + 2 * area), w(0x9A26 + 2 * area), w(0x9B8E + 2 * area)
        doors, y = [], 0
        while b[pos + y - 0x8000] != 0xFF:
            row, key = b[pos + y - 0x8000], b[pos + y + 1 - 0x8000]
            d0, d1 = b[dst + y - 0x8000], b[dst + y + 1 - 0x8000]
            f0, f1 = b[flg + y - 0x8000], b[flg + y + 1 - 0x8000]
            r6e, r6b = decode_dst(d1)
            door = dict(index=y // 2, row=row, key=key, world_x=world_x_for_key(key), dest_area=d0,
                        dest_6E=r6e, dest_6B=r6b, flag_52=f0, arrival=f1,
                        guardian=((f0 >> 4) & 7) if f0 & 0x80 else None, param_6C=f0 & 0x0F)
            if d0 == 0xFF:
                door['dest_area'] = 'return'
            doors.append(door)
            y += 2
        out.append(dict(area=area, doors=doors))
    return out


if __name__ == '__main__':
    data = areas()
    if '--json' in sys.argv:
        print(json.dumps(data, indent=1))
    else:
        for a in data:
            print(f"area {a['area']:2d}: {len(a['doors'])} doors")
            for d in a['doors']:
                print(f"   #{d['index']:2d} row {d['row']:2d} key {d['key']:02X} x={[hex(v) for v in d['world_x']]} -> "
                      f"{d['dest_area']} 6E={d['dest_6E']:02X} 6B={d['dest_6B']} 52={d['flag_52']:02X} "
                      f"guard={d['guardian']} 6C={d['param_6C']} arr={d['arrival']:02X}")
