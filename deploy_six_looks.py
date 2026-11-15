#!/usr/bin/env python3
"""Install the six-look v0.01 candidate over the accepted r16 device baseline.

Each file uses the tested atomic replacement core and its own immutable backup
and journal. Locale additions are additive to the accepted r16 resources. A failure stops
the sequence; it is never resumed automatically. No setting is rewritten here.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from local import ROOT, LAB, BUILD_ID, require, file_sha
from camera import native_module_replace as updater
from camera.native_install import save, save_json

BASELINE=LAB/'native-fl-releases/update-r16-vignette-21etjldm/write-1794732914378618000/16'

def package(build):
    parent=LAB/'native-fl-releases'
    parent.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='update-v001-six-looks-',dir=parent))
    view=BASELINE/'view-after.so'
    for revision,name in ((1701,'string_simplifiedchinese.uxc'),(1702,'string_english.uxc'),(17,None)):
        old=LAB/'native-fl-vignette-strings'/name if name else BASELINE/'new-module-readback.so'
        new=LAB/'native-fl-classic-strings'/name if name else build/'liba7-fl-module.so'
        proof=LAB/'native-fl-classic-strings/proof.json' if name else build/'proof.json'
        binding=out/str(revision)
        subprocess.run([sys.executable,'research/native_module_replace_bind.py','--revision',str(revision),
                        '--old',str(old),'--module',str(new),'--proof',str(proof),
                        '--view',str(view),'--out',str(binding)],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'research/native_module_replace_host_test.py',
                        '--binding',str(binding)],cwd=ROOT,check=True)
    save_json(out/'package.json',dict(kind='v001-six-looks',order=[1701,1702,17],
        bindings={str(v):file_sha(out/str(v)/'manifest.json') for v in (1701,1702,17)},
        source_sha256={'deploy_six_looks.py':file_sha(Path(__file__)),'research/six_look_settings.py':file_sha(ROOT/'research/six_look_settings.py')}))
    return out

def bindings(path):
    m=json.loads((path/'package.json').read_text())
    updater.pin_sources(m)
    require(m['kind']=='v001-six-looks' and m['order']==[1701,1702,17],'Unexpected update sequence.')
    result=[]
    for revision in m['order']:
        root=path/str(revision)
        require(file_sha(root/'manifest.json')==m['bindings'][str(revision)],'Package binding changed.')
        result.append(updater.Bundle(root))
    return result

def operate(camera,items,evidence):
    from camera.service import Factory
    evidence.mkdir(mode=0o700,parents=True,exist_ok=False)
    f=Factory(camera)
    # The transport-only guest switch may skip its unreliable extended model
    # query. Check exact maintenance identity before any camera-side payload;
    # each individual replacement independently repeats this same check.
    require(f.contents('/version.txt')==BUILD_ID and
            bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),
            'Camera model/build mismatch.')
    from research.six_look_settings import decoder,validate
    decode=decoder()
    before=[]
    for i in range(2):
        status,data=f.read(f'/setting/A7FL{i}.CFG',maximum=160)
        require(status==(0,0) and len(data)==128,'Expected existing preference slot missing.')
        before.append(data);save(evidence/f'preference-before-{i}.bin',data)
        settings=validate(decode,data)
        require(settings['schema']==5,'Expected installed r16 settings before first six-look upgrade.')
        save_json(evidence/f'preference-migration-{i}.json',settings)
    work=[]
    for i in range(2):
        status,data=f.read(f'/setting/A7FW{i}.CFG',maximum=160)
        require(status==(0,0) and len(data)==128,'Expected existing curve work record missing.')
        save(evidence/f'work-before-{i}.bin',data);work.append(data)
        validate(decode,data,work=True)
    # All target/backup/journal guards are checked before the first mutation.
    for item in items:
        updater.require_file(f,item.target,item.manifest['old'],evidence/f'old-{item.manifest["version"]}.bin')
        for name in (item.temporary,item.backup,item.journal):
            require(f.read(name)[0]==f.missing,'Previous transaction exists; review without retry: '+name)
    results=[]
    for item in items:
        results.append(updater.operate(camera,item,'replace',evidence/str(item.manifest['version']),True))
    for i,data in enumerate(before):
        after=f.contents(f'/setting/A7FL{i}.CFG',maximum=160)
        save(evidence/f'preference-after-{i}.bin',after)
        require(after==data,'Preferences changed during update.')
    for i,data in enumerate(work):
        after=f.contents(f'/setting/A7FW{i}.CFG',maximum=160)
        save(evidence/f'work-after-{i}.bin',after)
        require(after==data,'Work records changed during update.')
    result=dict(verified=True,work_records_unchanged=True,files=results,preferences_unchanged=True,cold_boot_required=True)
    save_json(evidence/'verified.json',result);updater.syncdir(evidence)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--build-dir',type=Path)
    group.add_argument('--package',type=Path)
    p.add_argument('--write-device',action='store_true')
    p.add_argument('--host-identity-check',action='store_true',
                   help='Verify exact model/build in maintenance mode instead of the guest extended query')
    args=p.parse_args()
    path=args.package.resolve() if args.package else package(args.build_dir.resolve())
    items=bindings(path)
    print('SIX_LOOK_PACKAGE',path,flush=True)
    if not args.write_device:return
    from camera import service,handoff
    result=None;previous=service.perform;previous_switch=handoff.SWITCH
    if args.host_identity_check:handoff.SWITCH+=' --host-identity-check'
    evidence=path/('write-'+str(time.time_ns()))
    def perform(camera,action):
        nonlocal result
        require(action=='settings-snapshot','Unexpected transport action.')
        device=camera.dev.driver.backend.dev;old=device.default_timeout;device.default_timeout=45000
        try:result=operate(camera,items,evidence)
        finally:device.default_timeout=old
    service.perform=perform
    try:handoff.run('settings-snapshot')
    finally:service.perform=previous;handoff.SWITCH=previous_switch
    require(result is not None,'No update result.')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
