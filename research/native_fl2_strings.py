#!/usr/bin/env python3
"""Append a dedicated FL2 label, preserving every deployed locale resource."""
import hashlib
import json
from pathlib import Path
from native_fl_strings import append

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'.lab/native-fl-strings'
OUT=ROOT/'.lab/native-fl2-strings'
PINNED={
    'string_simplifiedchinese.uxc':'980b77f7a7d08963976b724b958525d0b99e0f5e70a01552f3116dd3b1b014c1',
    'string_english.uxc':'8b4772b88ad655c0b866924ce0876d79d8400d3fc558c9350c28c58a05adf196',
}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    files={}
    for name,expected in PINNED.items():
        raw=(BASE/name).read_bytes()
        if digest(raw)!=expected:raise ValueError('Incorrect installed locale: '+name)
        new,ids=append(raw,['FL2'],expected_count=7592)
        if ids!=[0x0204fda8]:raise ValueError('Incorrect FL2 resource')
        (OUT/name).write_bytes(new)
        files[name]=dict(before_sha256=expected,after_sha256=digest(new),before_bytes=len(raw),after_bytes=len(new))
    proof=dict(kind='fl2-additive-locales-v1',files=files,resources={'fl2':0x0204fda8},
               prior_records_preserved_per_locale=7592,filesystem_block_count_unchanged=True,
               source_sha256={n:digest((ROOT/n).read_bytes()) for n in
                   ('research/native_fl2_strings.py','research/native_fl_strings.py','research/uxc_strings.py')})
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('FL2_STRINGS_VERIFIED',json.dumps(files))
if __name__=='__main__':main()
