#!/usr/bin/env python3
"""Offline tests of native installation review/staging CLI, with recorded evidence.

No USB imports or camera calls. Factory and camera objects below are in-memory
models. Existing saved device reports are read as input, never modified.
"""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from camera import native_install as cli

OUT=ROOT/'.lab/native-install-cli-test'
LIVE=ROOT/'.lab/native-install-bound/live-1794383297351589000'
checks=0
def check(ok,message):
    global checks
    checks+=1
    if not ok:raise AssertionError(message)
def rejects(action,message):
    try:action()
    except ValueError:check(True,message)
    else:check(False,message)
def record(binding,sequence,phase,created=0,published=0,backed=0):
    raw=struct.pack('<6I',0x4137464a,sequence,phase,created,published,backed)+bytes.fromhex(binding)
    return raw+hashlib.sha256(raw).digest()

class Factory:
    missing=(0,0x10000006)
    def __init__(self,files,install_files,report):
        self.files=dict(files);self.install_files=install_files;self.report=report
        self.reads=[];self.runs=[];self.read_errors={};self.readonly=True;self.after_install=None
    def read(self,path,maximum=1024*1024):
        self.reads.append((path,maximum))
        if path in self.read_errors:return self.read_errors[path],b''
        if path not in self.files:return self.missing,b''
        raw=self.files[path];check(len(raw)<=maximum,'mock Factory response respects requested bound')
        return (0,0),raw
    def contents(self,path):
        check(path=='/version.txt','only expected identity contents request')
        return cli.BUILD_ID
    def run(self,payload,name):
        self.runs.append((payload,name))
        if name=='a7mount.bin':
            check(payload==b'read-only-mount-probe','inspection invokes only mount probe')
            text=('/dev/nflasha15 /usr ext2 '+('ro' if self.readonly else 'rw')+',relatime,errors=continue 0 0\n').encode()
            return struct.pack('<Ii',0x41374d50,len(text))+text+bytes(16384-len(text))
        check(name=='a7install.bin','unknown mock payload execution')
        self.files.update(self.install_files)
        if self.after_install:self.after_install()
        return self.report

class Camera:
    def __init__(self,factory):
        self.factory=factory;self.settings_reads=0
        self.luts={key:bytes([key&255])*1280 for key in range(0x30004,0x30008)}
    def readBackup(self,key):
        if key==0x3e0005:return b'ILCE-7M3'+bytes(8)
        return self.luts[key]
    def getBackupPresetData(self,flag):
        check(flag is True,'expected snapshot request');self.settings_reads+=1;return b'mocked-settings'

def inspect(factory,bundle):
    with tempfile.TemporaryDirectory(dir=OUT) as folder:
        return cli.inspect(factory,bundle,Path(folder),b'read-only-mount-probe')

def operate(factory,bundle,operation,camera=None):
    camera=camera or Camera(factory)
    service=types.ModuleType('camera.service')
    service.Factory=lambda got: got.factory
    service.settings_ok=lambda data:check(data==b'mocked-settings','mock settings snapshot validated')
    with patch.dict(sys.modules,{'camera.service':service}):
        with tempfile.TemporaryDirectory(dir=OUT) as folder:
            return cli.operate(camera,bundle,operation,Path(folder),b'read-only-mount-probe')

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    bundle=cli.Bundle(ROOT/'.lab/native-install-bound',ROOT/'.lab/native-module/proof.json',
                      ROOT/'.lab/creative-icons-belt',ROOT/'.lab/native-fl-strings')
    binding=bundle.manifest['bundle_sha256']
    journal=(LIVE/'device-journal.bin').read_bytes();report=(LIVE/'report.bin').read_bytes()
    parsed=cli.journal_records(journal,binding)
    check(parsed['integrity_error'] is None and len(parsed['records'])==18 and parsed['last']['phase']==100,
          'actual saved 18-record device journal accepted')
    values=cli.install_report(report,binding)
    check(values['status']==0 and values['phase']==100 and values['readonly_confirmed']==1,
          'actual saved installer success report accepted')
    for size in range(len(journal)):
        result=cli.journal_records(journal[:size],binding)
        check(result['last'] is None or result['last']['phase']!=100,'truncated journal cannot retain final success')
        if size==0 or size%88:check(result['integrity_error'] is not None,'empty or torn journal detected')
        else:check(result['integrity_error'] is None,'complete valid prefix retained for review')
    for at in range(len(journal)):
        damaged=bytearray(journal);damaged[at]^=1;result=cli.journal_records(bytes(damaged),binding)
        check(result['integrity_error'] is not None,'every single-byte journal corruption detected')
        check(len(result['records'])==at//88,'corruption retains only valid prefix')
    rejects(lambda:cli.install_report(report[:-1],binding),'short report rejected')
    rejects(lambda:cli.install_report(report+b'\0',binding),'long report rejected')
    rejects(lambda:cli.install_report(report,'00'*32),'foreign report binding rejected')
    for at in (0,4,40):
        damaged=bytearray(report);damaged[at]^=1
        rejects(lambda:cli.install_report(bytes(damaged),binding),'foreign report identity rejected')
    check(cli.journal_records(journal,'00'*32)['integrity_error'] is not None,'foreign journal binding rejected')
    check(cli.journal_records(journal+record(binding,19,100,0,7,3),binding)['integrity_error'] is not None,
          'records after completed transaction rejected')
    check(cli.journal_records(record(binding,1,100,0,7,3),binding)['integrity_error'] is not None,
          'fabricated final-only journal rejected despite valid hash')
    for i,(phase,created,published,backed) in enumerate(cli.FORWARD):
        bad=record(binding,i+1,phase,created^1,published,backed)
        check(cli.journal_records(journal[:i*88]+bad,binding)['integrity_error'] is not None,
              'valid-hash impossible forward bitmap rejected')
    for count in range(1,18):
        raw=journal[:count*88]+record(binding,count+1,90,0,0,3)+record(binding,count+2,99,0,0,3)
        result=cli.journal_records(raw,binding)
        check(result['integrity_error'] is None and result['last']['phase']==99,
              'failure and partial-rollback bitmap journal retained')
    failure_after_sync=journal[:17*88]+record(binding,18,99,0,7,3)
    check(cli.journal_records(failure_after_sync,binding)['integrity_error'] is None,
          'remount failure ending after complete file verification retained')
    original={cli.FINAL[1]:(ROOT/'.lab/creative-icons-belt/string_simplifiedchinese.uxc').read_bytes(),
              cli.FINAL[2]:(ROOT/'.lab/creative-icons-belt/string_english.uxc').read_bytes(),
              cli.VIEW:(ROOT/'.lab/creative-icons-belt/viewUnified2.so').read_bytes()}
    installed={path:(bundle.directory/f'input{i}.bin').read_bytes() for i,path in enumerate(cli.FINAL)}
    installed.update({cli.BACKUPS[0]:original[cli.FINAL[1]],cli.BACKUPS[1]:original[cli.FINAL[2]],cli.JOURNAL:journal})
    staged={**original,**installed}
    factory=lambda files:Factory(files,installed,report)
    check(inspect(factory(original),bundle)['state']=='clean-original','original files recognized')
    outcome=inspect(factory(staged),bundle)
    check(outcome['state']=='staged' and not outcome['loader_file_active'] and not outcome['runtime_or_cold_boot_verified'],
          'complete module/locales/backups recognized without claiming runtime or loader')
    loaded=dict(staged);loaded[cli.VIEW]=(ROOT/'.lab/native-menu-boot-loader/viewUnified2.so').read_bytes()
    outcome=inspect(factory(loaded),bundle)
    check(outcome['state']=='staged' and outcome['loader_file_active'] and not outcome['runtime_or_cold_boot_verified'],
          'known loader file classified separately from execution proof')
    for path in (*cli.FINAL,*cli.BACKUPS,*cli.STAGE,cli.VIEW):
        damaged=dict(staged);damaged[path]=b'foreign bytes'
        check(inspect(factory(damaged),bundle)['state']=='review-required','every foreign critical file requires review')
    for path in (*cli.FINAL,*cli.BACKUPS,cli.VIEW):
        missing=dict(staged);missing.pop(path,None)
        check(inspect(factory(missing),bundle)['state']=='review-required','missing installed or backup file requires review')
    for raw in (b'',journal[:-1],journal[:-88],record(binding,1,100,0,7,3)):
        damaged=dict(staged);damaged[cli.JOURNAL]=raw
        check(inspect(factory(damaged),bundle)['state']=='review-required','incomplete journal prevents staged classification')
    rollback=dict(original);rollback[cli.JOURNAL]=journal[:88]+record(binding,2,90)+record(binding,3,99)
    check(inspect(factory(rollback),bundle)['state']=='rollback-files-match','complete restored preimages recognized without resuming')
    mounted=factory(staged);mounted.readonly=False
    check(inspect(mounted,bundle)['state']=='review-required','writable usr mount prevents success classification')
    unreadable=factory(staged);unreadable.read_errors[cli.FINAL[0]]=(-1,0)
    rejects(lambda:inspect(unreadable,bundle),'transport read error is not absence')
    for files in (staged,rollback,{**original,cli.JOURNAL:b''}):
        f=factory(files);cam=Camera(f)
        rejects(lambda:operate(f,bundle,'stage',cam),'stage never resumes an existing journal')
        check(not cam.settings_reads and all(name=='a7mount.bin' for _,name in f.runs),
              'rejected stage performs no installer or settings-save request')
    f=factory({**staged,cli.FINAL[0]:b'foreign'})
    check(operate(f,bundle,'rollback-review')['device_mutated'] is False and all(name=='a7mount.bin' for _,name in f.runs),
          'rollback review records state without recovery writes')
    f=factory({**staged,cli.JOURNAL:journal[:-1]})
    rejects(lambda:operate(f,bundle,'verify'),'verify rejects torn state rather than claiming success')
    f=factory(original);cam=Camera(f);outcome=operate(f,bundle,'stage',cam)
    check(outcome['verified'] and outcome['all_four_luts_unchanged'] and not outcome['loader_activated'],
          'mock clean stage verifies exact report, all files and four unchanged tables')
    check(sum(name=='a7install.bin' for _,name in f.runs)==1 and cam.settings_reads==1,
          'mock successful stage invokes installer exactly once')
    f=factory(original);cam=Camera(f);f.after_install=lambda:cam.luts.__setitem__(0x30004,bytes(1280))
    rejects(lambda:operate(f,bundle,'stage',cam),'changed calibration after stage cannot be reported successful')
    for argv in (['stage'],['verify','--write-device'],['rollback-review','--write-device']):
        with patch.object(sys,'argv',['native-install',*argv]),patch.object(cli,'Bundle',side_effect=AssertionError('bundle accessed before write guard')):
            rejects(cli.main,'write-device guard precedes all bundle and device access')
    # A subprocess import barrier proves that --offline cannot even load USB or
    # maintenance transport code, for both default verification and stage preview.
    guard='''import builtins,runpy,sys
old=builtins.__import__
def safe(name,*args,**kwargs):
 if name.startswith(('usb','pmca')) or name in ('camera.service','camera.handoff'):
  raise RuntimeError('Offline operation imported camera transport: '+name)
 return old(name,*args,**kwargs)
builtins.__import__=safe
sys.argv=['native-install']+sys.argv[1:]
runpy.run_module('camera.native_install',run_name='__main__')
'''
    outputs=[]
    for args in (['--offline'],['stage','--write-device','--offline']):
        run=subprocess.run([sys.executable,'-c',guard,*args],cwd=ROOT,capture_output=True,text=True,check=True)
        value=json.loads(run.stdout);check(value['camera_contacted'] is False and value['local_proofs_verified'],
                                         'offline invocation verified local proofs without transport imports')
        outputs.append(value)
    source_files=['camera/native_install.py','research/native_install_cli_test.py','local.py']
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    proof={'source_sha256':{p:h(ROOT/p) for p in source_files},'checks':checks,
           'recorded_evidence_sha256':{p.name:h(p) for p in (LIVE/'device-journal.bin',LIVE/'report.bin')},
           'bundle_manifest_sha256':h(bundle.manifest_path),'offline_outputs':outputs,
           'camera_contacted':False,'scope':'Pure parser and mocked Factory/Camera tests using existing saved device journal/report and exact local file artifacts; no USB or live writes.'}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('NATIVE_INSTALL_CLI_CHECKS',checks)
    print('NATIVE_INSTALL_CLI_TESTS_PASSED')

if __name__=='__main__':main()
