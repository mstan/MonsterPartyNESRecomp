"""List and fingerprint only release-owned files for the writable Linux runtime."""
import hashlib
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
entries = []
digest = hashlib.sha256()
for source_dir, target_prefix in [('usr/bin', ''), ('usr/lib', 'lib/')]:
    for path in sorted((root / source_dir).rglob('*')):
        if not path.is_file():
            continue
        source = path.relative_to(root).as_posix()
        target = target_prefix + path.relative_to(root / source_dir).as_posix()
        if any(c in source + target for c in '|\r\n') or '..' in Path(target).parts:
            raise ValueError('Unsafe payload path')
        entries.append(f'{source}|{target}')
        digest.update(target.encode() + b'\0' + path.read_bytes())
(root / 'payload-files').write_text('\n'.join(entries) + '\n', newline='\n')
(root / 'payload-id').write_text(digest.hexdigest() + '\n', newline='\n')
