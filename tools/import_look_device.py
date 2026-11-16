#!/usr/bin/env python3
"""Check or import a recipe on a supported, already modified ILCE-7M3."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import zlib

from look_recipes import ROOT, LOOKS, FIELDS, candidate_crc, decode, encode, load_recipe, recipe, sha
sys.path.insert(0,str(ROOT))
from local import LAB, require
from camera.native_install import save, save_json
from camera.native_module_replace import syncdir
from camera import native_status

PATHS = tuple(f'/setting/A7F{bank}{slot}.CFG' for bank in ('L','W') for slot in (0,1))
MODULE = 'e5a530c3fe3790b829d3ee0cca7ff2628bf6a7a24f952c4f3cf46bcad8316feb'


def prepare(before, identity, build, desired, only=None):
    require(len(before)==4,'Expected two preferences and two work records.')
    records = [decode(raw,identity) for raw in before[:2]]
    require(records[0][0]!=records[1][0] or before[0]==before[1],'Conflicting settings generations.')
    slot = max(range(2),key=lambda i: records[i][0])
    generation,mode,banks,crc = records[slot]
    require(generation<0xfffffffe,'Generation counter exhausted.')
    historical = []
    for raw in before[2:]:
        require(len(raw)==128 and raw[:8]==b'A7FLW001' and zlib.crc32(raw[:124])==int.from_bytes(raw[124:],'little'),
                'Invalid work record.')
        pref = b'A7FLP001'+raw[8:124]
        historical.append(decode(pref+struct.pack('<I',zlib.crc32(pref)),identity))
    checked = set()
    for _,m,b,c in records+historical:
        key = (m,tuple(tuple(row) for row in b),c)
        if key not in checked:
            require(candidate_crc(build,identity,m,b)==c,'Existing record LUT differs from the matching build.')
            checked.add(key)
    if only is not None:
        bank,field = only
        new_banks = [row.copy() for row in banks]
        new_banks[bank][field] = desired[1][bank][field]
        desired = mode,new_banks
    next_mode,next_banks = desired
    if (mode,banks)==desired:
        return slot,records[slot],None
    new_crc = candidate_crc(build,identity,next_mode,next_banks)
    after = encode(generation+1,next_mode,next_banks,new_crc,identity)
    require(decode(after,identity)==(generation+1,next_mode,next_banks,new_crc),'Candidate round-trip failed.')
    return slot,records[slot],after


def build_writer(out,before,target,after):
    arr = lambda raw: '{'+','.join(map(str,raw))+'}'
    text = 'static const unsigned char before[4][128]={'+','.join(map(arr,before))+'};\n'
    text += f'static const unsigned target={target};\nstatic const unsigned char after[128]={arr(after)};\n'
    (out/'recipe-data.h').write_text(text)
    path = out/'recipe-writer.so'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
         '-nostdlib','-shared','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror',
         '-Wl,--no-undefined','-Wl,-z,noexecstack','-DA7_RECIPE_BOUND','-DA7_FL_FILM_CONTROLS',
         '-I'+str(out),str(ROOT/'payloads/a7-fl-recipe-import.c'),str(ROOT/'payloads/a7-fl-posix.c'),
         '-o',str(path)],check=True)
    return path.read_bytes()


def run(a,desired):
    from camera import handoff, service
    proof_path = a.binding/'module-proof.json'
    proof = json.loads(proof_path.read_text())
    require(proof['module_sha256']==MODULE and proof['look_count']==6 and proof['preference_schema']==6,
            'Only the accepted v0.01 L/M/S module is supported.')
    header = a.build/'a7-fl-module-data.h'
    require(sha(header.read_bytes())==proof['artifact_sha256'][header.name],'Local LUT build does not match the module.')
    profile = native_status.Profile(LAB/'native-install-bound',proof_path,a.probe,a.bundle,
        replacement_binding=a.binding,capture_proof=LAB/'lut3d-fl2-reference-private/proof.json')
    identity = hashlib.sha256(profile.original[0]).digest()
    out = LAB/'recipe-device-import'/str(time.time_ns())
    out.mkdir(mode=0o700,parents=True)
    print('IMPORT_EVIDENCE',out,flush=True)

    def perform(camera,action):
        require(action=='settings-snapshot','Unexpected maintenance action.')
        factory = service.Factory(camera)
        report = native_status.inspect_camera(camera,profile,out,True)
        before = [factory.contents(path,maximum=160) for path in PATHS]
        for i,raw in enumerate(before):
            save(out/f'before-{i}.bin',raw)
        slot,(generation,mode,banks,_),after = prepare(before,identity,a.build,desired,a.only)
        rt = report.get('runtime') or {}
        clean = (report['state']=='resident-ready' and rt.get('fault')==0 and rt.get('last_error')==0
              and rt.get('dirty')==0 and rt.get('generation')==generation and rt.get('mode')==mode
              and rt.get('parameters')==banks[mode-1 if mode else 0][:8])
        _,next_mode,next_banks,_ = decode(after,identity) if after is not None else (generation,mode,banks,0)
        result = dict(saved_generation=generation,current_recipe=recipe(mode,banks),
             changed_looks=[i+1 for i,(old,new) in enumerate(zip(banks,next_banks)) if old!=new],
             active_changed=mode!=next_mode,dirty=rt.get('dirty'),ready=bool(clean),
             settings_written=False)
        save_json(out/'preflight.json',result)
        if after is None:
            print('IMPORT_PREFLIGHT',json.dumps({k:v for k,v in result.items() if k!='current_recipe'}),flush=True)
            print('IMPORT_SAVED_VALUES_MATCH',flush=True)
            return
        save(out/'candidate.cfg',after)
        writer = build_writer(out,before,1-slot,after)
        print('IMPORT_PREFLIGHT',json.dumps({k:v for k,v in result.items() if k!='current_recipe'}),flush=True)
        if not a.write:
            return
        require(clean,'Save or cancel the current menu edits, reconnect, then check again.')
        # Check the same clean resident state after generating the candidate.
        recheck = out/'recheck'
        recheck.mkdir()
        fresh = native_status.inspect_camera(camera,profile,recheck,True)
        require(fresh['state']==report['state'] and fresh['runtime']==rt,'Resident changed during preflight.')
        save_json(out/'write-intent.json',dict(target=PATHS[1-slot],candidate=sha(after),generation=generation+1))
        syncdir(out)
        raw = factory.run(writer,'a7recipe.bin')
        save(out/'writer-report.bin',raw)
        require(len(raw)==8 and struct.unpack('<Ii',raw)==(0x41375249,0),
                'Write result unverified; do not retry before checking both slots.')
        observed = [factory.contents(path,maximum=160) for path in PATHS]
        expected = before.copy()
        expected[1-slot] = after
        require(observed==expected,'Readback differs; inspect the retained records before any retry.')
        for i,data in enumerate(observed):
            save(out/f'after-{i}.bin',data)
        require(decode(observed[1-slot],identity)[:3]==(generation+1,next_mode,next_banks),
                'Imported recipe differs.')
        save_json(out/'verified.json',dict(settings_written=True,reboot_required=True,generation=generation+1,
                  candidate_sha256=sha(after),original_slot_unchanged=True,work_records_unchanged=True))
        syncdir(out)
        print('IMPORT_VERIFIED_REBOOT_REQUIRED',flush=True)

    prev,sw = service.perform,handoff.SWITCH
    try:
        service.perform = perform
        handoff.SWITCH += ' --host-identity-check'
        handoff.run('settings-snapshot')
    finally:
        service.perform,handoff.SWITCH = prev,sw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recipe',type=Path,required=True)
    p.add_argument('--binding',type=Path,required=True)
    p.add_argument('--probe',type=Path,required=True)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--bundle',type=Path,default=LAB/'native-fl-01')
    p.add_argument('--write',action='store_true',help='Write only the inactive settings slot after preflight.')
    p.add_argument('--only',choices=[f'{look}.{field}' for look in LOOKS for field in FIELDS],
                   metavar='LOOK.FIELD',help='Import one setting and preserve the current selection and all other values.')
    a = p.parse_args()
    if a.only:
        look,field = a.only.split('.')
        a.only = LOOKS.index(look),FIELDS.index(field)
    run(a,load_recipe(a.recipe))


if __name__=='__main__':
    main()
