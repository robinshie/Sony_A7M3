#!/usr/bin/env python3
"""Prepare/apply/restore a two-byte native YAP LPF diagnostic, not a feature.

Requires explicit --live for USB operations. No firmware replacement or save
command is sent. Native global saves may persist backup RAM; restoration remains
required after the observation, including after a restart.
"""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from local import BUILD_ID, require, sha

IDS=(0x30032,0x30033,0x30139)
SIZES=(2560,5120,5120)
TARGET=IDS[0]
OFFSETS=(0x26,0x27)
ORIGINAL_SHA='a03046cb8a5198131c8e81ad0a3a063702fce19821e11aa9a2b9d0669cfef755'
MODULE_SHA='f3e2d657a83569f19ddafcd843a40601f1d953da0a20a8f8617c5e299e73a063'


def candidate(original):
    require(len(original)==2560 and sha(original)==ORIGINAL_SHA,
            'Requires the observed unchanged YAP table')
    require(all(original[i]==1 for i in OFFSETS),'Unknown original LPF selectors')
    changed=bytearray(original)
    for i in OFFSETS:changed[i]=0
    require([i for i,(a,b) in enumerate(zip(original,changed)) if a!=b]==list(OFFSETS),
            'Unexpected diagnostic delta')
    return bytes(changed)


def durable(path,data):
    with path.open('xb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    require(path.read_bytes()==data,'Local recovery readback failed')


def prepare(args):
    from pmca.backup import BackupFile
    require(not args.bundle.exists(),'Use a new private bundle directory')
    raw=args.settings.read_bytes();backup=BackupFile(io.BytesIO(raw))
    require(backup.revision==4 and backup.size==len(raw),'Expected complete BK4')
    original={}
    for key,size in zip(IDS,SIZES):
        prop=backup.getProperty(key)
        require(prop.attr==8 and len(prop.data)==size,'Unexpected property layout')
        original[key]=bytes(prop.data)
    changed=candidate(original[TARGET]);stream=io.BytesIO(raw);modified=BackupFile(stream)
    modified.setProperty(TARGET,changed);modified.updateChecksum();new=stream.getvalue()
    check=BackupFile(io.BytesIO(new))
    for key,prop in backup.listProperties():
        require(check.getProperty(key)==(prop._replace(data=changed) if key==TARGET else prop),
                'Unrelated property changed')
    args.bundle.mkdir(parents=True,mode=0o700)
    artifacts={'original-settings.bin':raw,'candidate-settings.bin':new,'candidate.bin':changed,
               **{f'{k:08x}.bin':v for k,v in original.items()}}
    for name,data in artifacts.items():durable(args.bundle/name,data)
    subprocess.run([sys.executable,str(ROOT/'research/yap_lpf_native.py'),
        '--avcam',str(args.avcam),'--settings',str(args.bundle/'candidate-settings.bin'),
        '--pmca',str(args.pmca),'--out',str(args.bundle/'qemu')],check=True)
    manifest=dict(schema=1,kind='YAP_LPF_1_TO_0_DIAGNOSTIC',build=BUILD_ID.decode(),
        offsets=list(OFFSETS),files={n:sha(d) for n,d in artifacts.items()},
        source_sha256={n:sha((ROOT/n).read_bytes()) for n in
                       ('research/yap_lpf_probe.py','research/yap_lpf_probe_test.py')},
        proof_sha256=sha((args.bundle/'qemu/proof.json').read_bytes()),
        effect_verified=False,firmware_written=False)
    durable(args.bundle/'manifest.json',(json.dumps(manifest,indent=2)+'\n').encode())
    print('YAP_LPF_PREPARED',args.bundle)


class Experiment:
    def __init__(self,path):
        self.path=path;m=json.loads((path/'manifest.json').read_text())
        require(m['schema']==1 and m['kind']=='YAP_LPF_1_TO_0_DIAGNOSTIC' and
                m['build']==BUILD_ID.decode() and m['offsets']==list(OFFSETS),'Wrong diagnostic identity')
        for name,digest in m['files'].items():
            require(Path(name).name==name and sha((path/name).read_bytes())==digest,'Artifact changed')
        self.original={k:(path/f'{k:08x}.bin').read_bytes() for k in IDS}
        self.changed=(path/'candidate.bin').read_bytes()
        require(self.changed==candidate(self.original[TARGET]),'Candidate is not the bounded diagnostic')
        self.manifest=m

    def proof(self):
        p=self.path/'qemu/proof.json';require(sha(p.read_bytes())==self.manifest['proof_sha256'],'Proof changed')
        proof=json.loads(p.read_text())
        for sources in (self.manifest['source_sha256'],proof['source_sha256']):
            for name,digest in sources.items():require(sha((ROOT/name).read_bytes())==digest,'Source changed: '+name)
        for name,key in (('yap-lpf.elf','elf_sha256'),('qemu.log','qemu_log_sha256')):
            require(sha((p.parent/name).read_bytes())==proof[key],'QEMU artifact changed')
        require(proof['private_tables_executed'] and
                proof['private_backup']['settings_sha256']==self.manifest['files']['candidate-settings.bin'],
                'Candidate table was not executed offline')

    def snapshot(self,camera,current):
        from pmca.backup import BackupFile
        raw=bytes(camera.getBackupPresetData(True));bk=BackupFile(io.BytesIO(raw))
        require(bk.revision==4 and bk.size==len(raw),'Incomplete live BK4')
        for key,size in zip(IDS,SIZES):
            value=bytes(camera.readBackup(key));prop=bk.getProperty(key)
            require(len(value)==size and prop.attr==8 and prop.data==value,'Live property disagreement')
            require(value==(current if key==TARGET else self.original[key]),'Unknown YAP table state')
        return raw

    def event(self,directory,name,**extra):
        durable(directory/f'{time.time_ns()}-{name}.json',
                (json.dumps(dict(event=name,**extra),indent=2)+'\n').encode())

    def operate(self,camera,action):
        require(action in ('apply','restore','status'),'Unknown operation')
        if action=='apply':self.proof()
        current=bytes(camera.readBackup(TARGET));old=self.original[TARGET]
        partial=len(current)==len(old) and all(v in (a,b) for v,a,b in zip(current,old,self.changed))
        require(current in (old,self.changed) or (action=='restore' and partial),
                'Unknown preimage; refusing overwrite')
        before=self.snapshot(camera,current)
        if action=='status':
            print('YAP_LPF_STATE','original' if current==old else 'diagnostic');return
        folder=self.path/f'{action}-{time.time_ns()}';folder.mkdir(mode=0o700)
        durable(folder/'before-settings.bin',before)
        target=self.changed if action=='apply' else old
        self.event(folder,'prepared',action=action,current_sha256=sha(current),target_sha256=sha(target))
        if current==target:
            print('YAP_LPF_ALREADY_MATCHED',action);return
        self.event(folder,'write-started')
        try:
            camera.writeBackup(TARGET,target)
            durable(folder/'after-settings.bin',self.snapshot(camera,target))
        except BaseException as failure:
            self.event(folder,'failed',error=str(failure))
            if action=='apply':
                try:
                    camera.writeBackup(TARGET,old)
                    durable(folder/'restored-settings.bin',self.snapshot(camera,old))
                    self.event(folder,'automatic-restore-verified')
                except BaseException as recovery:
                    self.event(folder,'restore-required',error=str(recovery))
                    print('YAP_LPF_RESTORE_REQUIRED',self.path,flush=True)
            raise
        self.event(folder,'readback-verified')
        print('YAP_LPF_'+action.upper()+'_VERIFIED',folder,flush=True)
        print('TWO_SELECTOR_BYTES; NO_FIRMWARE_WRITE; NO_SAVE_COMMAND; PERSISTENCE_UNKNOWN',flush=True)


def main():
    os.umask(0o077)
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('prepare','apply','restore','status'))
    for name in ('bundle','settings','avcam','pmca'):
        cli.add_argument('--'+name,type=lambda s:Path(s).expanduser().resolve(),required=name=='bundle')
    cli.add_argument('--live',action='store_true');args=cli.parse_args()
    if args.pmca:sys.path.insert(0,str(args.pmca))
    if args.action=='prepare':
        require(args.settings and args.avcam and args.pmca and not args.live,'Prepare needs local inputs only')
        prepare(args);return
    require(args.live,'USB operation requires --live')
    experiment=Experiment(args.bundle)
    from camera import service,handoff
    def collect(camera,unused):
        f=service.Factory(camera)
        require(f.contents('/version.txt')==BUILD_ID and
                bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model/build')
        if args.action=='apply':require(sha(f.contents('/usr/lib/a7fl.so'))==MODULE_SHA,'Unexpected resident revision')
        experiment.operate(camera,args.action)
    service.perform=collect;previous=handoff.SWITCH;handoff.SWITCH+=' --host-identity-check'
    try:handoff.run('settings-snapshot')
    finally:handoff.SWITCH=previous


if __name__=='__main__':main()
