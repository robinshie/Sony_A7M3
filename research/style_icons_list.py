#!/usr/bin/env python3
"""Complete the existing slot-3 Neutral/RW icon family, preserving other styles."""
import argparse
import json
import struct
from pathlib import Path

from style_icons import Images, badge, encode, swizzle
from menu_lazy import sha

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/style-icons-list'
BEFORE_SHA = '5b6e94231de326292babb99aeae97f9fa98bc09d086368f6336a58405a5a4ea7'
TARGETS = {0x5c7c8: (58, 50), 0x5c823: (70, 60), 0x5c87e: (116, 100)}


def patch(data):
    if sha(data) != BEFORE_SHA:
        raise ValueError('Expected the installed first RW icon package')
    old = Images(data)
    result = bytearray(data)
    spans = []
    for key, (width, height) in TARGETS.items():
        at, flags, w, h, begin, available = old.records[key]
        if (w, h) != (width, height) or flags != 0xe0000000:
            raise ValueError('Wrong slot-3 icon format')
        blob = encode(swizzle(w, h, badge('RW', w, h, w > 100)))
        if len(blob) > available:
            raise ValueError('Replacement exceeds its own image stream')
        result[begin:begin + len(blob)] = blob
        struct.pack_into('<I', result, at + 12, len(blob))
        spans += [(begin, begin + len(blob)), (at + 12, at + 16)]
    # The entire index, all pointers/dimensions, and all other resource bytes
    # remain intact, including first-pass RW icons and the unrelated Neutral.
    cursor = 0
    for begin, end in sorted(spans):
        if begin < cursor or data[cursor:begin] != result[cursor:begin]:
            raise ValueError('Unrelated bytes changed')
        cursor = end
    if data[cursor:] != result[cursor:] or len(data) != len(result):
        raise ValueError('Unrelated suffix or file length changed')
    new = Images(result)
    for key, (w, h) in TARGETS.items():
        if new.pixels(key) != (w, h, badge('RW', w, h, w > 100)):
            raise ValueError('Replacement pixels differ')
    for key in (0x5c76d, 0x5c049, 0x5c04a, 0x5c7af, 0x5c80a, 0x5c865, 0x5c8c0):
        if new.pixels(key) != old.pixels(key):
            raise ValueError('Existing RW or base Neutral icon changed')
    return bytes(result)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--usr', required=True, type=Path)
    args = cli.parse_args()
    prior = ROOT / '.lab/creative-icons'
    manifest = json.loads((prior / 'manifest.json').read_text())
    base_proof = ROOT / '.lab/menu-icons/proof.json'
    if sha(base_proof.read_bytes()) != manifest['native_proof_sha256']:
        raise ValueError('Prior native proof changed')
    proof = json.loads(base_proof.read_text())
    for path, digest in proof['source_sha256'].items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError('Prior tested source changed: ' + path)
    # These are the actual stock table references, not a guess from icon order.
    references = {'lib/viewUnified7.so': [(0x8c834, 0x0205c7c8)],
                  'lib/viewUnified2.so': [(0xa594e8, 0x0205c87e), (0xa594f8, 0x0205c823)]}
    library_hashes = {}
    for path, entries in references.items():
        data = (args.usr / path).read_bytes()
        library_hashes[path] = sha(data)
        for offset, expected in entries:
            if struct.unpack_from('<I', data, offset)[0] != expected:
                raise ValueError('Native icon table mismatch: ' + path)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    data = patch((prior / 'image_cmn_43.uxc').read_bytes())
    (OUT / 'image_cmn_43.uxc').write_bytes(data)
    view = (prior / 'viewUnified2.so').read_bytes()
    if sha(view) != manifest['files']['/lib/viewUnified2.so']['after_sha256']:
        raise ValueError('Previous UI code changed')
    (OUT / 'viewUnified2.so').write_bytes(view)
    source = dict(proof['source_sha256'])
    source['research/style_icons_list.py'] = sha(Path(__file__).read_bytes())
    result = {'scope': 'Only three remaining slot-3 RW image resources; native code is unchanged',
              'base_native_proof_sha256': sha(base_proof.read_bytes()),
              'source_sha256': source, 'table_library_sha256': library_hashes,
              'references': references, 'targets': [hex(x) for x in TARGETS],
              'icon_sha256': BEFORE_SHA,
              'init_file_offset': Images(data).records[0x5c7c8][0] + 12,
              'files': {n: sha((OUT / n).read_bytes()) for n in ('viewUnified2.so', 'image_cmn_43.uxc')}}
    (OUT / 'proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print('RW_LIST_ICONS_PASSED: 58x50, 70x60, 116x100; all other resource bytes preserved')


if __name__ == '__main__':
    main()
