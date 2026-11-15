#!/usr/bin/env python3
"""Prepare six-look locale files locally from exact r16 inputs; no camera I/O."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def apply(raw, patch):
    if len(raw)!=patch['before']['size'] or sha(raw)!=patch['before']['sha256']:
        raise ValueError('Locale is not the exact r16 baseline')
    data=bytearray(raw)
    end=0
    for change in patch['changes']:
        offset=change['offset'];value=base64.b64decode(change['data'],validate=True)
        if offset<end or offset>len(data) or not value:
            raise ValueError('Invalid locale delta')
        data[offset:offset+len(value)]=value
        end=offset+len(value)
    result=bytes(data)
    if len(result)!=patch['after']['size'] or sha(result)!=patch['after']['sha256']:
        raise ValueError('Patched locale hash mismatch')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-dir',type=Path,required=True)
    p.add_argument('--patch-dir',type=Path,default=Path(__file__).resolve().parents[1]/'locales')
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    outputs={}
    for name in ('string_simplifiedchinese.uxc','string_english.uxc'):
        patch=json.loads((args.patch_dir/(name+'.json')).read_text())
        outputs[name]=apply((args.baseline_dir/name).read_bytes(),patch)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    for name,raw in outputs.items():
        (args.output_dir/name).write_bytes(raw)
        print(name,sha(raw))

if __name__=='__main__':
    main()
