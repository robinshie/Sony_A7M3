#!/usr/bin/env python3
"""Offline failure injection for the LPF experiment's write/recovery transaction."""
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research import yap_lpf_probe as probe


def main():
    old=bytearray((i*37+11)&255 for i in range(2560))
    old[0x26]=old[0x27]=1;old=bytes(old)
    # Synthetic table pin exists only in this offline process. No USB imports.
    probe.ORIGINAL_SHA=probe.sha(old)
    changed=probe.candidate(old);assert [i for i,(a,b) in enumerate(zip(old,changed)) if a!=b]==[0x26,0x27]
    for bad in (old[:-1],old+b'\0',bytes([old[0]^1])+old[1:]):
        try:probe.candidate(bad)
        except (RuntimeError,ValueError):pass
        else:raise AssertionError('Unpinned candidate accepted')
    cases=3
    with tempfile.TemporaryDirectory(prefix='a7-yap-test-') as tmp:
        for scenario in ('normal','already','unknown','other-changed','partial-write',
                         'readback-failure','recovery-failure','partial-restore',
                         'partial-apply','wrong-size','proof-rejected'):
            cases+=1
            folder=Path(tmp)/scenario;folder.mkdir()
            exp=probe.Experiment.__new__(probe.Experiment)
            exp.path=folder;exp.original={probe.IDS[0]:old,probe.IDS[1]:bytes(5120),probe.IDS[2]:bytes(5120)}
            exp.changed=changed
            def proof():
                if scenario=='proof-rejected':raise ValueError('Test proof mismatch')
            exp.proof=proof
            class Camera:
                def __init__(self):self.values=dict(exp.original);self.writes=[];self.snapshots=0
                def readBackup(self,key):return self.values[key]
                def writeBackup(self,key,value):
                    assert key==probe.TARGET and list(folder.glob('*/before-settings.bin'))
                    self.writes.append(value)
                    if scenario in ('partial-write','recovery-failure') and len(self.writes)==1:
                        raw=bytearray(old);raw[0x26]=0;self.values[key]=bytes(raw)
                        raise OSError('Injected partial USB acceptance')
                    if scenario=='recovery-failure' and len(self.writes)==2:raise OSError('Disconnected')
                    self.values[key]=value
            cam=Camera()
            def snapshot(camera,current):
                camera.snapshots+=1
                if scenario=='readback-failure' and camera.snapshots==2:raise ValueError('Injected readback mismatch')
                for key in probe.IDS:
                    if camera.values[key]!=(current if key==probe.TARGET else exp.original[key]):raise ValueError('Unknown property')
                return b'OFFLINE-SNAPSHOT-'+bytes([camera.snapshots])
            exp.snapshot=snapshot
            action='apply'
            if scenario=='already':cam.values[probe.TARGET]=changed
            if scenario=='unknown':cam.values[probe.TARGET]=bytes([old[0]^1])+old[1:]
            if scenario=='other-changed':cam.values[probe.IDS[1]]=bytes([1])+bytes(5119)
            if scenario in ('partial-restore','partial-apply'):
                raw=bytearray(old);raw[0x26]=0;cam.values[probe.TARGET]=bytes(raw)
                if scenario=='partial-restore':action='restore'
            if scenario=='wrong-size':cam.values[probe.TARGET]=old[:-1]
            failed=False
            try:exp.operate(cam,action)
            except (ValueError,RuntimeError,OSError):failed=True
            if scenario=='normal':
                assert not failed and cam.writes==[changed] and cam.values[probe.TARGET]==changed
                exp.operate(cam,'restore');assert cam.writes==[changed,old] and cam.values[probe.TARGET]==old
            elif scenario=='already':assert not failed and not cam.writes
            elif scenario=='partial-restore':assert not failed and cam.writes==[old] and cam.values[probe.TARGET]==old
            elif scenario in ('partial-write','readback-failure'):
                assert failed and cam.writes==[changed,old] and cam.values[probe.TARGET]==old
                assert list(folder.glob('*/restored-settings.bin'))
            elif scenario=='recovery-failure':
                assert failed and cam.writes==[changed,old] and list(folder.glob('*/*-restore-required.json'))
            else:assert failed and not cam.writes
    print('YAP_LPF_TRANSACTION_PASSED cases='+str(cases))


if __name__=='__main__':main()
