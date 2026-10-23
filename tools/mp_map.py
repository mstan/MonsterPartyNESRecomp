"""Decode a Monster Party area's background feature grid from a save state.

Mirrors the original lookup (USA), with the area's pointers taken from live RAM:
  7:DBE4/DCA0  feature at (Y, world X): rows Y>>4 0..11 read the map, rows
               12..13 are feature 4 and lower rows 0
  7:D7CA       page record = ($62) + (page + $51) * 16, in PRG bank $40
  7:D75E/D848  column id = page record[(X>>4) & $0E]; column = ($60) + id * 24
  7:DCCB       X bit 4 selects the second 12-row half of the column
  7:DCEB       feature = ($68)[metatile]
Feature 6 is a door (4:$834F raises the door request $53), 7 the round exit
(4:$830A needs $58 == 0).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycstate  # noqa: E402
from dis6502 import load  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class AreaMap:
    def __init__(self, ram, rom=ROOT / 'monsterparty.nes'):
        self.banks = load(rom)
        self.ram = ram
        self.bank = ram[0x40]
        w = lambda a: ram[a] | ram[a + 1] << 8
        self.cols, self.pages, self.feat = w(0x60), w(0x62), w(0x68)
        self.page_offset = ram[0x51]

    def byte(self, addr):
        if addr >= 0xC000:
            return self.banks[7][addr - 0xC000]
        return self.banks[self.bank][addr - 0x8000]

    def metatile(self, world_x, y):
        page, lo = world_x >> 8, world_x & 0xFF
        record = (self.pages + (((page + self.page_offset) << 4) & 0xFFF)) & 0xFFFF
        col_id = self.byte(record + ((lo >> 4) & 0x0E))
        col = (self.cols + col_id * 24) & 0xFFFF
        half = 12 if (lo >> 3) & 2 else 0
        return self.byte(col + half + (y >> 4))

    def feature(self, world_x, y):
        row = y >> 4
        if row >= 14:
            return 0
        if row >= 12:
            return 4
        return self.byte(self.feat + self.metatile(world_x, y))

    def grid(self, pages=16):
        return [[self.feature(x, row * 16) for x in range(0, pages * 256, 16)] for row in range(12)]


def find(state, pages=16, kinds=(6, 7)):
    m = AreaMap(cycstate.ram(Path(state).read_bytes()))
    g = m.grid(pages)
    return [(k, row, x * 16) for row in range(12) for x in range(len(g[row])) for k in kinds if g[row][x] == k]


if __name__ == '__main__':
    for state in sys.argv[1:]:
        hits = find(state)
        print(Path(state).stem, [(k, r, hex(x)) for k, r, x in hits])
