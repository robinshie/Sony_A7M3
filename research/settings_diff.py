#!/usr/bin/env python3
"""Compare two private, checksum-verified BK4 snapshots without modifying them."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--pmca', type=Path, required=True)
    cli.add_argument('before', type=Path)
    cli.add_argument('after', type=Path)
    cli.add_argument('--show-small-values', action='store_true',
                     help='Include changed values of at most 8 bytes; keep the output private')
    args = cli.parse_args()
    sys.path.insert(0, str(args.pmca.resolve()))
    from pmca.backup import BackupFile

    def read(path):
        data = path.read_bytes()
        b = BackupFile(io.BytesIO(data))
        if b.revision != 4 or b.size != len(data):
            raise ValueError('Expected a complete, checksum-verified BK4 snapshot')
        return b, dict(b.listProperties()), hashlib.sha256(data).hexdigest()

    left, old, old_sha = read(args.before)
    right, new, new_sha = read(args.after)
    if left.header.version != right.header.version or old.keys() != new.keys():
        raise ValueError('Snapshot versions or property sets do not match')
    changes = []
    for key, before in old.items():
        after = new[key]
        if before == after:
            continue
        row = {'id': f'0x{key:08x}', 'before_size': len(before.data), 'after_size': len(after.data),
               'before_sha256': hashlib.sha256(before.data).hexdigest(),
               'after_sha256': hashlib.sha256(after.data).hexdigest(),
               'attributes_changed': before.attr != after.attr,
               'reset_data_changed': before.resetData != after.resetData}
        if args.show_small_values and max(len(before.data),len(after.data)) <= 8:
            row.update(before_hex=before.data.hex(),after_hex=after.data.hex())
        changes.append(row)
    print(json.dumps({'before_sha256':old_sha,'after_sha256':new_sha,
                      'changed_properties':changes,
                      'note':'Differences are candidates, not validated write addresses.'},indent=2))


if __name__ == '__main__':
    main()
