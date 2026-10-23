"""Read and fixture cartridge CYCSTATE save states (engine runner/cyc/cyc_state.c).

Offsets are qualified for the pinned engine's MSVC x64 HwMachine layout and
re-checked against --mem-out by tests/coverage/check_state_layout.py. A fixture
writes only CPU work RAM and journals every changed byte beside the new state;
it never patches guest code.
"""
import hashlib
import json
from pathlib import Path
import struct

HW_RAM_OFFSET = 23      # uint8 tick, align; uint64 cycles; uint16 addr; five uint8 fields
HW_LENGTH = 2072


def chunks(data):
    if data[:8] != b'CYCSTATE':
        raise ValueError('not a CYCSTATE file')
    at = 32
    while at < len(data):
        tag, length = struct.unpack_from('<4sI', data, at)
        at += 8
        if at + length > len(data):
            raise ValueError('truncated state chunk')
        yield tag, at, length
        at += length
        if tag == b'END ':
            return
    raise ValueError('missing END chunk')


def _hw(data):
    for tag, at, length in chunks(data):
        if tag == b'HW  ':
            if length != HW_LENGTH:
                raise ValueError(f'unqualified HwMachine layout ({length} bytes)')
            return at
    raise ValueError('missing HW chunk')


def ram(data):
    at = _hw(data)
    return bytes(data[at + HW_RAM_OFFSET:at + HW_RAM_OFFSET + 0x800])


def cycles(data):
    return struct.unpack_from('<Q', data, _hw(data) + 8)[0]


def fixture(source, destination, writes, purpose):
    """Copy a state with explicit work-RAM writes {addr: value}; journal them."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('fixture destination already exists')
    data = bytearray(source.read_bytes())
    at = _hw(data) + HW_RAM_OFFSET
    changes = []
    for addr, value in sorted(writes.items()):
        if not 0 <= addr < 0x800 or not 0 <= value <= 255:
            raise ValueError('only CPU work-RAM bytes may be written')
        changes.append(dict(address=f'{addr:04X}', before=data[at + addr], after=value))
        data[at + addr] = value
    destination.write_bytes(data)
    destination.with_suffix('.fixture.json').write_text(json.dumps(dict(
        source=str(source.resolve()), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        fixture_sha256=hashlib.sha256(data).hexdigest(), purpose=purpose, changes=changes,
        evidence_scope='Assisted setup; not an unassisted traversal or victory.'), indent=2) + '\n')
    return destination
