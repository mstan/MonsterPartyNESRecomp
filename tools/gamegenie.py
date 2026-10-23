"""Decode NES Game Genie codes (6 or 8 letters) to address/value/compare."""
import sys
L = 'APZLGITYEOXUKSVN'
def decode(code):
    n = [L.index(c) for c in code.upper()]
    addr = 0x8000 + (((n[3] & 7) << 12) | ((n[5] & 7) << 8) | ((n[4] & 8) << 8) | ((n[2] & 7) << 4)
                     | ((n[1] & 8) << 4) | (n[4] & 7) | (n[3] & 8))
    if len(n) == 6:
        val = ((n[1] & 7) << 4) | ((n[0] & 8) << 4) | (n[0] & 7) | (n[5] & 8)
        return addr, val, None
    val = ((n[1] & 7) << 4) | ((n[0] & 8) << 4) | (n[0] & 7) | (n[7] & 8)
    cmp = ((n[7] & 7) << 4) | ((n[6] & 8) << 4) | (n[6] & 7) | (n[5] & 8)
    return addr, val, cmp
if __name__ == '__main__':
    for c in sys.argv[1:]:
        a, v, k = decode(c)
        print(f'{c}: ${a:04X} = ${v:02X}' + (f' if ${k:02X}' if k is not None else ''))
