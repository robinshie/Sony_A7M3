#!/usr/bin/env python3
"""Append a dedicated FL3 label, preserving every deployed locale resource."""
import hashlib
import json
from pathlib import Path
from native_fl_strings import append

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'.lab/native-fl2-strings'
OUT=ROOT/'.lab/native-fl3-strings'
PINNED={
    'string_simplifiedchinese.uxc':'c992cd53f905df46f98d13800d4f899c93d9e4e50cf2e35135d8e6f557ec006b',
    'string_english.uxc':'d3c4bb0a71e4355d3bf394a14543abc850f76eccb0ec72e0c64f31f97f41f9ef',
}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    files={}
    for name,expected in PINNED.items():
        raw=(BASE/name).read_bytes()
        if digest(raw)!=expected:raise ValueError('Incorrect installed locale: '+name)
        new,ids=append(raw,['FL3（徕卡胶片）' if 'chinese' in name else 'FL3 (Leica Film)'],expected_count=7593,allow_new_blocks=True)
        if ids!=[0x0204fda9]:raise ValueError('Incorrect FL3 resource')
        (OUT/name).write_bytes(new)
        files[name]=dict(before_sha256=expected,after_sha256=digest(new),before_bytes=len(raw),after_bytes=len(new))
    proof=dict(kind='fl3-additive-locales-v1',files=files,resources={'fl3':0x0204fda9},
               prior_records_preserved_per_locale=7593,filesystem_block_count_unchanged=False,
               source_sha256={n:digest((ROOT/n).read_bytes()) for n in
                   ('research/native_fl3_strings.py','research/native_fl_strings.py','research/uxc_strings.py')})
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('FL3_STRINGS_VERIFIED',json.dumps(files))
if __name__=='__main__':main()
