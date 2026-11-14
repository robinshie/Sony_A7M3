#!/usr/bin/env python3
"""One-time r13 -> r14 update: independent curves for all three looks.

Each file uses the tested atomic replacement core and its own immutable backup
and journal. Locale additions are backwards compatible with r11. A failure stops
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

BASELINE=LAB/'native-fl-releases/update-r13-curves-sbz58fzf/write-1794664646457339000/13'

def package(build):
    parent=LAB/'native-fl-releases'
    parent.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='update-r14-all-curves-',dir=parent))
    view=BASELINE/'view-after.so'
    for revision,name in ((14,None),):
        old=LAB/'native-fl3-strings'/name if name else BASELINE/'new-module-readback.so'
        new=LAB/'native-fl-curve-strings'/name if name else build/'liba7-fl-module.so'
        proof=LAB/'native-fl-curve-strings/proof.json' if name else build/'proof.json'
        binding=out/str(revision)
        subprocess.run([sys.executable,'research/native_module_replace_bind.py','--revision',str(revision),
                        '--old',str(old),'--module',str(new),'--proof',str(proof),
                        '--view',str(view),'--out',str(binding)],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'research/native_module_replace_host_test.py',
                        '--binding',str(binding)],cwd=ROOT,check=True)
    save_json(out/'package.json',dict(kind='r14-all-curves',order=[14],
        bindings={str(v):file_sha(out/str(v)/'manifest.json') for v in (14,)},
        source_sha256={'deploy_fl_all_curves.py':file_sha(Path(__file__))}))
    return out

def bindings(path):
    m=json.loads((path/'package.json').read_text())
    updater.pin_sources(m)
    require(m['kind']=='r14-all-curves' and m['order']==[14],'Unexpected update sequence.')
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
    before=[]
    for i in range(2):
        status,data=f.read(f'/setting/A7FL{i}.CFG',maximum=160)
        require(status==(0,0) and len(data)==128,'Expected existing preference slot missing.')
        before.append(data);save(evidence/f'preference-before-{i}.bin',data)
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
    result=dict(verified=True,files=results,preferences_unchanged=True,cold_boot_required=True)
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
    print('FL3_CURVE_PACKAGE',path,flush=True)
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
