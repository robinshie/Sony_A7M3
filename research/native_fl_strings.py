#!/usr/bin/env python3
"""Append FL labels to UXC v7 without changing any prior text or block count."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from uxc_strings import Strings

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    'root': ('创意外观', 'Creative Look'),
    'fl': ('FL（实验版）', 'FL Experimental'),
    'contrast': ('对比度', 'Contrast'),
    'highlights': ('高光', 'Highlights'),
    'shadows': ('阴影', 'Shadows'),
    'fade': ('褪色', 'Fade'),
    'saturation': ('饱和度', 'Saturation'),
    'sharpness': ('锐度', 'Sharpness'),
    'range': ('锐度范围', 'Sharpness Range'),
    'clarity': ('清晰度', 'Clarity'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def append(data, labels):
    old = Strings(data)
    if old.count != 7582 or not labels or old.count+len(labels)>8191:
        raise ValueError('Unexpected pinned index size')
    index_end = old.entries[-1][0]+old.entries[-1][1]
    if any(data[index_end:old.start]):
        raise ValueError('Nonzero index alignment padding')
    if any(not isinstance(s,str) or not s or '\0' in s for s in labels):
        raise ValueError('Invalid added label')
    n = len(labels)
    result = bytearray(data[:index_end]+bytes(4*n)+data[index_end:])
    packed = struct.unpack_from('<I', data,12)[0]
    struct.pack_into('<I', result,12,((packed>>13)+n)<<13 | (old.count+n))
    start = old.start+4*n
    resources = []
    for i,text in enumerate(labels):
        key = 0x4e000+old.count+i
        offset = (len(result)-start)//4
        struct.pack_into('<HH',result,index_end+4*i,0x8000|(offset>>16),offset&65535)
        result.extend(key.to_bytes(3,'little')+b'\x1e'+text.encode()+b'\0')
        result.extend(bytes(-len(result)%4))
        resources.append(key|0x02000000)
    parsed = Strings(result)
    if parsed.count!=old.count+n or parsed.short_count!=old.short_count:
        raise ValueError('Index shape changed unexpectedly')
    if result[start:start+len(data)-old.start]!=data[old.start:]:
        raise ValueError('Prior string record bytes changed')
    for i in range(old.count):
        key = 0x4e000+i
        if parsed.text(key)!=old.text(key):
            raise ValueError('Prior assigned or unassigned resource changed')
    for key,text in zip(resources,labels):
        if parsed.text(key&0xffffff)!=text:
            raise ValueError('Added resource lookup failed')
    if math.ceil(len(result)/1024)!=math.ceil(len(data)/1024):
        raise ValueError('Added text would allocate another filesystem block')
    return bytes(result), resources


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--base',type=Path,default=ROOT/'.lab/creative-icons-belt')
    cli.add_argument('--out',type=Path,default=ROOT/'.lab/native-fl-strings')
    args=cli.parse_args(); m=json.loads((args.base/'manifest.json').read_text())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'proof.json').unlink(missing_ok=True)
    files={};mapping=None
    for col,name in enumerate(('string_simplifiedchinese.uxc','string_english.uxc')):
        raw=(args.base/name).read_bytes()
        if sha(raw)!=m['files']['/share/app/'+name]['after_sha256']:
            raise ValueError('Wrong deployed locale preimage')
        result,ids=append(raw,[pair[col] for pair in LABELS.values()])
        current=dict(zip(LABELS,ids))
        if mapping is not None and current!=mapping:raise ValueError('Locale resource mismatch')
        mapping=current;(args.out/name).write_bytes(result)
        files[name]={'before_sha256':sha(raw),'after_sha256':sha(result),
                     'before_bytes':len(raw),'after_bytes':len(result)}
    proof={'files':files,'resources':mapping,'prior_records_preserved_per_locale':7582,
           'filesystem_block_count_unchanged':True,'source_sha256':{
               name:sha((ROOT/name).read_bytes()) for name in ('research/native_fl_strings.py','research/uxc_strings.py')}}
    (args.out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('NATIVE_FL_STRINGS_VERIFIED',json.dumps(mapping))


if __name__=='__main__':main()
