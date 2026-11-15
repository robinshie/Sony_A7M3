#!/usr/bin/env python3
"""Exercise six-bank preservation and pre-write failures without USB access."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import deploy_auto_size as deploy

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--snapshot',type=Path,required=True)
a=p.parse_args()
out=ROOT/'.lab/deploy-auto-size-test';out.mkdir(exist_ok=True)
paths=[f'/setting/A7FL{i}.CFG' for i in range(2)]+[f'/setting/A7FW{i}.CFG' for i in range(2)]
original={name:(a.snapshot/f'setting-{i}.bin').read_bytes() for i,name in enumerate(paths)}
profile=deploy.updater.REVISIONS[18]
old=(deploy.BASELINE/'new-module-readback.so').read_bytes()
assert len(old)==profile['old_size'] and hashlib.sha256(old).hexdigest()==profile['old_sha']
item=SimpleNamespace(target='/usr/lib/a7fl.so',temporary='/usr/lib/'+profile['temporary'],
    backup='/usr/lib/'+profile['backup'],journal='/setting/'+profile['journal'],
    manifest=dict(version=18,old=dict(size=len(old),sha256=profile['old_sha'])))
checks=0

class Camera:
    def __init__(self):
        self.files=dict(original);self.files[item.target]=old;self.writes=0
        self.fail=False;self.change=None
    def readBackup(self,key):
        assert key==0x3e0005
        return b'ILCE-7M3'+bytes(8)

class Factory:
    missing=(0,0x10000006)
    def __init__(self,c):self.c=c
    def read(self,path,maximum=1048576):
        if path not in self.c.files:return self.missing,b''
        b=self.c.files[path]
        assert len(b)<=maximum
        return (0,0),b
    def contents(self,path,maximum=1048576):
        if path=='/version.txt':return deploy.BUILD_ID
        status,b=self.read(path,maximum)
        assert status==(0,0)
        return b

def writer(camera,b,operation,evidence,write):
    assert b is item and operation=='replace' and write is True
    camera.writes+=1
    if camera.fail:raise ValueError('Injected writer failure')
    if camera.change:camera.files[camera.change]=bytes(128)
    return dict(verified=True)

def run(camera,label,accepted):
    global checks
    with tempfile.TemporaryDirectory(dir=out) as temp:
        evidence=Path(temp)/'evidence'
        try:
            result=deploy.operate(camera,[item],evidence)
        except ValueError:
            assert not accepted and not (evidence/'verified.json').exists(),label
        else:
            assert accepted and result['preferences_unchanged'] and result['work_records_unchanged'],label
            for i in range(2):
                assert (evidence/f'preference-before-{i}.bin').read_bytes()==(evidence/f'preference-after-{i}.bin').read_bytes()
                assert (evidence/f'work-before-{i}.bin').read_bytes()==(evidence/f'work-after-{i}.bin').read_bytes()
        checks+=1

with patch.dict(sys.modules,{'camera.service':SimpleNamespace(Factory=Factory)}), patch.object(deploy.updater,'operate',writer):
    c=Camera();run(c,'preserve all four records',True);assert c.writes==1
    for name in paths:
        c=Camera();c.files[name]=bytes(128);run(c,'invalid settings stop before writer',False);assert c.writes==0
        c=Camera();del c.files[name];run(c,'missing settings stop before writer',False);assert c.writes==0
        c=Camera();c.change=name;run(c,'changed settings prevent success',False);assert c.writes==1
    for name in (item.temporary,item.backup,item.journal):
        c=Camera();c.files[name]=b'existing';run(c,'existing transaction stops',False);assert c.writes==0
    c=Camera();c.files[item.target]=old[:-1]+bytes([old[-1]^1]);run(c,'wrong baseline stops',False);assert c.writes==0
    c=Camera();c.fail=True;run(c,'writer failure does not retry',False);assert c.writes==1
proof=dict(passed=True,checks=checks,camera_contacted=False,
    source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                  ('deploy_auto_size.py','research/deploy_auto_size_test.py','research/six_look_settings.py')},
    scope='Real schema-6 decode; mocked camera storage and atomic writer. Four records preserved; invalid/missing records, wrong baseline, existing transaction and writer failure stop.')
(out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print('AUTO_SIZE_DEPLOY_PASSED',checks)
