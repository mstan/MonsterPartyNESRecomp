"""Small 6502 disassembler for reading Monster Party (USA) PRG banks.

Bank 7 is fixed at $C000 (MMC1 PRG mode 3 after the reset stub); banks 0-6
switch into $8000. Usage:
  python tools/dis6502.py monsterparty.nes 7 C1F3 60
  python tools/dis6502.py monsterparty.nes 2 8000 40
  python tools/dis6502.py monsterparty.nes find 9E          # absolute/zp refs
"""
import sys
from pathlib import Path

MODES = {
    'imp': 0, 'acc': 0, 'imm': 1, 'zp': 1, 'zpx': 1, 'zpy': 1, 'izx': 1, 'izy': 1,
    'rel': 1, 'abs': 2, 'abx': 2, 'aby': 2, 'ind': 2,
}
OPS = {}
def op(code, name, mode): OPS[code] = (name, mode)
for c, n, m in [
    (0x00,'BRK','imp'),(0x01,'ORA','izx'),(0x05,'ORA','zp'),(0x06,'ASL','zp'),(0x08,'PHP','imp'),(0x09,'ORA','imm'),(0x0A,'ASL','acc'),(0x0D,'ORA','abs'),(0x0E,'ASL','abs'),
    (0x10,'BPL','rel'),(0x11,'ORA','izy'),(0x15,'ORA','zpx'),(0x16,'ASL','zpx'),(0x18,'CLC','imp'),(0x19,'ORA','aby'),(0x1D,'ORA','abx'),(0x1E,'ASL','abx'),
    (0x20,'JSR','abs'),(0x21,'AND','izx'),(0x24,'BIT','zp'),(0x25,'AND','zp'),(0x26,'ROL','zp'),(0x28,'PLP','imp'),(0x29,'AND','imm'),(0x2A,'ROL','acc'),(0x2C,'BIT','abs'),(0x2D,'AND','abs'),(0x2E,'ROL','abs'),
    (0x30,'BMI','rel'),(0x31,'AND','izy'),(0x35,'AND','zpx'),(0x36,'ROL','zpx'),(0x38,'SEC','imp'),(0x39,'AND','aby'),(0x3D,'AND','abx'),(0x3E,'ROL','abx'),
    (0x40,'RTI','imp'),(0x41,'EOR','izx'),(0x45,'EOR','zp'),(0x46,'LSR','zp'),(0x48,'PHA','imp'),(0x49,'EOR','imm'),(0x4A,'LSR','acc'),(0x4C,'JMP','abs'),(0x4D,'EOR','abs'),(0x4E,'LSR','abs'),
    (0x50,'BVC','rel'),(0x51,'EOR','izy'),(0x55,'EOR','zpx'),(0x56,'LSR','zpx'),(0x58,'CLI','imp'),(0x59,'EOR','aby'),(0x5D,'EOR','abx'),(0x5E,'LSR','abx'),
    (0x60,'RTS','imp'),(0x61,'ADC','izx'),(0x65,'ADC','zp'),(0x66,'ROR','zp'),(0x68,'PLA','imp'),(0x69,'ADC','imm'),(0x6A,'ROR','acc'),(0x6C,'JMP','ind'),(0x6D,'ADC','abs'),(0x6E,'ROR','abs'),
    (0x70,'BVS','rel'),(0x71,'ADC','izy'),(0x75,'ADC','zpx'),(0x76,'ROR','zpx'),(0x78,'SEI','imp'),(0x79,'ADC','aby'),(0x7D,'ADC','abx'),(0x7E,'ROR','abx'),
    (0x81,'STA','izx'),(0x84,'STY','zp'),(0x85,'STA','zp'),(0x86,'STX','zp'),(0x88,'DEY','imp'),(0x8A,'TXA','imp'),(0x8C,'STY','abs'),(0x8D,'STA','abs'),(0x8E,'STX','abs'),
    (0x90,'BCC','rel'),(0x91,'STA','izy'),(0x94,'STY','zpx'),(0x95,'STA','zpx'),(0x96,'STX','zpy'),(0x98,'TYA','imp'),(0x99,'STA','aby'),(0x9A,'TXS','imp'),(0x9D,'STA','abx'),
    (0xA0,'LDY','imm'),(0xA1,'LDA','izx'),(0xA2,'LDX','imm'),(0xA4,'LDY','zp'),(0xA5,'LDA','zp'),(0xA6,'LDX','zp'),(0xA8,'TAY','imp'),(0xA9,'LDA','imm'),(0xAA,'TAX','imp'),(0xAC,'LDY','abs'),(0xAD,'LDA','abs'),(0xAE,'LDX','abs'),
    (0xB0,'BCS','rel'),(0xB1,'LDA','izy'),(0xB4,'LDY','zpx'),(0xB5,'LDA','zpx'),(0xB6,'LDX','zpy'),(0xB8,'CLV','imp'),(0xB9,'LDA','aby'),(0xBA,'TSX','imp'),(0xBC,'LDY','abx'),(0xBD,'LDA','abx'),(0xBE,'LDX','aby'),
    (0xC0,'CPY','imm'),(0xC1,'CMP','izx'),(0xC4,'CPY','zp'),(0xC5,'CMP','zp'),(0xC6,'DEC','zp'),(0xC8,'INY','imp'),(0xC9,'CMP','imm'),(0xCA,'DEX','imp'),(0xCC,'CPY','abs'),(0xCD,'CMP','abs'),(0xCE,'DEC','abs'),
    (0xD0,'BNE','rel'),(0xD1,'CMP','izy'),(0xD5,'CMP','zpx'),(0xD6,'DEC','zpx'),(0xD8,'CLD','imp'),(0xD9,'CMP','aby'),(0xDD,'CMP','abx'),(0xDE,'DEC','abx'),
    (0xE0,'CPX','imm'),(0xE1,'SBC','izx'),(0xE4,'CPX','zp'),(0xE5,'SBC','zp'),(0xE6,'INC','zp'),(0xE8,'INX','imp'),(0xE9,'SBC','imm'),(0xEA,'NOP','imp'),(0xEC,'CPX','abs'),(0xED,'SBC','abs'),(0xEE,'INC','abs'),
    (0xF0,'BEQ','rel'),(0xF1,'SBC','izy'),(0xF5,'SBC','zpx'),(0xF6,'INC','zpx'),(0xF8,'SED','imp'),(0xF9,'SBC','aby'),(0xFD,'SBC','abx'),(0xFE,'INC','abx'),
]: op(c, n, m)

FMT = {'imp': '', 'acc': 'A', 'imm': '#${:02X}', 'zp': '${:02X}', 'zpx': '${:02X},X', 'zpy': '${:02X},Y',
       'izx': '(${:02X},X)', 'izy': '(${:02X}),Y', 'abs': '${:04X}', 'abx': '${:04X},X', 'aby': '${:04X},Y',
       'ind': '(${:04X})'}


def load(rom):
    raw = Path(rom).read_bytes()
    prg = raw[16:16 + raw[4] * 16384]
    return [prg[i * 16384:(i + 1) * 16384] for i in range(raw[4])]


def base(bank, nbanks):
    return 0xC000 if bank == nbanks - 1 else 0x8000


def decode(data, org, pc):
    off = pc - org
    if off < 0 or off >= len(data):
        return None
    b = data[off]
    if b not in OPS:
        return (1, f'.db ${b:02X}', None, None)
    name, mode = OPS[b]
    n = MODES[mode]
    ops = data[off + 1:off + 1 + n]
    if len(ops) < n:
        return None
    if mode == 'rel':
        tgt = (pc + 2 + (ops[0] - 256 if ops[0] & 128 else ops[0])) & 0xFFFF
        return (2, f'{name} ${tgt:04X}', mode, tgt)
    val = ops[0] if n == 1 else (ops[0] | ops[1] << 8) if n == 2 else None
    text = name + (' ' + FMT[mode].format(val) if FMT[mode] else (' A' if mode == 'acc' else ''))
    return (1 + n, text, mode, val)


def listing(banks, bank, pc, count):
    data, org = banks[bank], base(bank, len(banks))
    out = []
    for _ in range(count):
        d = decode(data, org, pc)
        if d is None:
            break
        size, text, _, _ = d
        raw = ' '.join(f'{x:02X}' for x in data[pc - org:pc - org + size])
        out.append(f'{bank}:{pc:04X}  {raw:<9} {text}')
        pc += size
    return out


def find(banks, addr):
    """Every linear-sweep decode that references addr (heuristic; verify by listing)."""
    for bank, data in enumerate(banks):
        org = base(bank, len(banks))
        for off in range(len(data)):
            d = decode(data, org, org + off)
            if not d or d[2] is None:
                continue
            if d[3] == addr and d[2] not in ('imm', 'rel'):
                print(f'{bank}:{org + off:04X}  {d[1]}')


if __name__ == '__main__':
    banks = load(sys.argv[1])
    if sys.argv[2] == 'find':
        find(banks, int(sys.argv[3], 16))
    else:
        print('\n'.join(listing(banks, int(sys.argv[2]), int(sys.argv[3], 16), int(sys.argv[4]) if len(sys.argv) > 4 else 40)))
