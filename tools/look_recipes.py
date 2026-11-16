#!/usr/bin/env python3
"""Export, preview and prepare six Creative Look recipes without camera I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
LOOKS = ('FL', 'FL2', 'FL3', 'FL4', 'FL5', 'FL6')
FIELDS = ('contrast', 'highlights', 'shadows', 'fade', 'saturation', 'sharpness',
          'sharpness_range', 'clarity', 'grain', 'halation', 'black', 'curve_shadow',
          'midtone', 'curve_highlight', 'white', 'vignette')
LABELS = ('对比度','高光','阴影','褪色','饱和度','锐度','锐度范围','清晰度',
          '颗粒','光晕','黑位','暗部','中间调','亮部','白位','暗角')
LOW = (-9,-9,-9,0,-9,-3,1,0,0,-9,-9,-9,-9,-9,-9,-9)
HIGH = (9,9,9,9,9,3,5,9,9,9,9,9,9,9,9,9)
BUILD = b'37114_13.2026020901'.ljust(24, b'\0')
MAGIC = b'A7FLP001'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2)+'\n'


def unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('Duplicate JSON key: '+k)
        result[k] = v
    return result


def load_recipe(path):
    with path.open('rb') as file:
        raw = file.read(32769)
    if len(raw)>32768:
        raise ValueError('Recipe JSON exceeds 32 KiB')
    p = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(p,dict) or p.keys()!={'format','active','looks'} or p['format']!='sony-a7-look-recipes/v1':
        raise ValueError('Unknown recipe format')
    if p['active'] not in ('off',*LOOKS):
        raise ValueError('Unknown active look')
    looks = p['looks']
    if not isinstance(looks,dict) or looks.keys()!=set(LOOKS):
        raise ValueError('Exactly six named looks are required')
    banks = []
    for look in LOOKS:
        row = looks[look]
        if not isinstance(row,dict) or row.keys()!=set(FIELDS):
            raise ValueError(look+' must contain all 16 named controls')
        values = [row[n] for n in FIELDS]
        for n,v,lo,hi in zip(FIELDS,values,LOW,HIGH):
            if type(v) is not int or not lo<=v<=hi:
                raise ValueError(f'{look}.{n} requires an integer in [{lo}, {hi}]')
        banks.append(values)
    return ('off',*LOOKS).index(p['active']),banks


def recipe(mode,banks):
    return dict(format='sony-a7-look-recipes/v1',active=('off',*LOOKS)[mode],
                looks={look:dict(zip(FIELDS,row)) for look,row in zip(LOOKS,banks)})


def decode(raw, identity):
    if (len(raw)!=128 or raw[:9]!=MAGIC+b'\x06' or raw[62:94]!=identity or
        raw[94:118]!=BUILD or raw[122:124]!=b'\0\0' or
        int.from_bytes(raw[124:],'little')!=zlib.crc32(raw[:124])):
        raise ValueError('Bad schema-6 CRC, model build or factory identity')
    generation,mode = struct.unpack_from('<IB',raw,9)
    if not generation or mode>6:
        raise ValueError('Invalid generation or look')
    banks = []
    for code in struct.unpack_from('<6Q',raw,14):
        row = []
        for lo,hi in zip(LOW,HIGH):
            code,v = divmod(code,hi-lo+1)
            row.append(v+lo)
        if code:
            raise ValueError('Invalid packed look')
        banks.append(row)
    return generation,mode,banks,struct.unpack_from('<I',raw,118)[0]


def encode(generation,mode,banks,crc,identity):
    codes = []
    for row in banks:
        code = 0
        for v,lo,hi in reversed(tuple(zip(row,LOW,HIGH))):
            code = code*(hi-lo+1)+v-lo
        codes.append(code)
    prefix = MAGIC+b'\x06'+struct.pack('<IB6Q',generation,mode,*codes)
    prefix += identity+BUILD+struct.pack('<I2x',crc)
    return prefix+struct.pack('<I',zlib.crc32(prefix))


def tables_for(build,banks):
    sys.path.insert(0,str(ROOT/'research'))
    from classic_look_preview import extract_tables
    return extract_tables(build,banks,include_off_crc=True)


def candidate_crc(build,identity,mode,banks):
    tables = tables_for(build,banks)
    if hashlib.sha256(tables[0]).digest()!=identity:
        raise ValueError('Local build does not match factory LUT identity')
    return zlib.crc32(tables[mode or 7])


def baseline(a,identity):
    raws = [p.read_bytes() for p in a.slots]
    rows = [decode(raw,identity) for raw in raws]
    if rows[0][0]==rows[1][0] and raws[0]!=raws[1]:
        raise ValueError('Conflicting saved slots at the same generation')
    slot = max(range(2),key=lambda i:rows[i][0])
    return slot,raws,rows[slot]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action',required=True)
    for name in ('export','import','preview'):
        cmd = sub.add_parser(name)
        if name!='preview':
            cmd.add_argument('--slots',nargs=2,type=Path,required=True,metavar=('A7FL0','A7FL1'))
        if name!='export':
            cmd.add_argument('--recipe',type=Path,required=True)
            cmd.add_argument('--build',type=Path,required=True)
        cmd.add_argument('--bundle',type=Path,default=ROOT/'.lab/native-fl-01')
        cmd.add_argument('--out',type=Path,required=True)
        if name=='preview':
            cmd.add_argument('--font',type=Path,default=Path('/System/Library/Fonts/Hiragino Sans GB.ttc'))
    a = p.parse_args()
    identity = hashlib.sha256((a.bundle/'00030004.bin').read_bytes()).digest()
    if a.action=='preview':
        sys.path.insert(0,str(ROOT/'research'))
        from classic_look_preview import render
        from native_fl import Codec
        _,banks = load_recipe(a.recipe)
        tables = tables_for(a.build,banks)
        if hashlib.sha256(tables[0]).digest()!=identity:
            raise ValueError('Local build does not match factory LUT identity')
        if a.out.exists():
            raise ValueError('Output already exists')
        render(a.out,tables[:7],Codec((a.bundle/'codec.bin').read_bytes()),a.font,
               '配方色彩及五点曲线模拟｜非真机 JPEG，不含拍后效果')
        return
    slot,raws,(generation,mode,banks,crc) = baseline(a,identity)
    if a.action=='export':
        with a.out.open('x',encoding='utf-8') as f:
            f.write(json_text(recipe(mode,banks)))
        return
    new_mode,new_banks = load_recipe(a.recipe)
    if generation>=0xfffffffe:
        raise ValueError('Generation counter exhausted')
    if candidate_crc(a.build,identity,mode,banks)!=crc:
        raise ValueError('Saved candidate CRC does not match the local build')
    new_crc = candidate_crc(a.build,identity,new_mode,new_banks)
    raw = encode(generation+1,new_mode,new_banks,new_crc,identity)
    if decode(raw,identity)!=(generation+1,new_mode,new_banks,new_crc):
        raise ValueError('Generated record failed round-trip')
    changes = []
    for look,old,new in zip(LOOKS,banks,new_banks):
        fields = [{'field':n,'menu':label,'from':x,'to':y}
                  for n,label,x,y in zip(FIELDS,LABELS,old,new) if x!=y]
        if fields:
            changes.append(dict(look=look,controls=fields))
    a.out.mkdir(exist_ok=False)
    (a.out/'candidate.cfg').write_bytes(raw)
    (a.out/'plan.json').write_text(json_text(dict(
        target_model='ILCE-7M3',firmware='4.04',offline_only=True,
        baseline_slot_sha256=[sha(x) for x in raws],candidate_sha256=sha(raw),
        intended_inactive_slot=1-slot,from_generation=generation,
        to_generation=generation+1,active=('off',*LOOKS)[new_mode],changes=changes)),
        encoding='utf-8')
    print(f'Prepared {sum(len(x["controls"]) for x in changes)} changes; camera untouched')


if __name__=='__main__':
    try:
        main()
    except (ValueError,OSError) as e:
        raise SystemExit(str(e)) from e
