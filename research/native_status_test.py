#!/usr/bin/env python3
"""Offline resident-report/prefs/LUT diagnostics tests; never imports USB."""
import ctypes
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera import native_status as status
from camera.native_install import Bundle
from research.elf32 import ELF
OUT=ROOT/'.lab/native-status-test'
checks=0
def check(ok,message):
    global checks
    checks+=1
    if not ok:raise AssertionError(message)
def rejects(fn,message):
    try:fn()
    except ValueError:check(True,message)
    else:check(False,message)
class Preference(ctypes.Structure):
    _fields_=[('generation',ctypes.c_uint32),('enabled',ctypes.c_int),('parameters',ctypes.c_int*8),('candidate_crc',ctypes.c_uint32)]


def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    bundle=Bundle(ROOT/'.lab/native-install-bound',ROOT/'.lab/native-module/proof.json',ROOT/'.lab/creative-icons-belt',ROOT/'.lab/native-fl-strings')
    data=ROOT/'.lab/native-fl-01';base=(data/'candidate.bin').read_bytes();codec=(data/'codec.bin').read_bytes()
    originals=[(data/f'{key:08x}.bin').read_bytes() for key in range(0x30004,0x30008)]
    digest=hashlib.sha256(originals[0]).digest();build=status.BUILD_ID+bytes(24-len(status.BUILD_ID))
    wrapper=OUT/'reference.c';wrapper.write_text('''#include "a7-fl-color.h"
int generate(const uint8_t *base,const uint8_t *codec,const int *p,uint8_t *output){
 uint16_t expansion[129];for(unsigned i=0;i<129;i++)expansion[i]=codec[2*i]|(uint16_t)codec[2*i+1]<<8;
 A7FLColorParams values={p[0],p[1],p[2],p[3],p[4]};
 return a7_fl_adjust_lut(base,1280,expansion,codec+258,&values,output,1280);
}
''')
    subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-I',str(ROOT/'payloads'),str(wrapper),
                    str(ROOT/'payloads/a7-fl-runtime.c'),str(ROOT/'payloads/a7-fl-runtime-prefs.c'),'-o',str(OUT/'reference.so')],check=True)
    lib=ctypes.CDLL(str(OUT/'reference.so'))
    lib.generate.argtypes=[ctypes.c_void_p]*4;lib.generate.restype=ctypes.c_int
    lib.a7_fl_preference_encode.argtypes=[ctypes.c_void_p,ctypes.POINTER(Preference),ctypes.c_void_p,ctypes.c_void_p]
    lib.a7_fl_preference_decode.argtypes=[ctypes.POINTER(Preference),ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
    lib.a7_fl_preference_choose.argtypes=[ctypes.POINTER(Preference),ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
    cases=[[0]*5]
    for index in range(5):
        for value in range(status.LOW[index],status.HIGH[index]+1):
            p=[0]*5;p[index]=value;cases.append(p)
    rng=random.Random(70404)
    cases += [[rng.randint(status.LOW[i],status.HIGH[i]) for i in range(5)] for _ in range(240)]
    for p in cases:
        out=ctypes.create_string_buffer(1280);values=(ctypes.c_int*5)(*p)
        check(lib.generate(base,codec,values,out)==0,'actual C LUT generator accepted controls')
        generated=status.adjusted_lut(base,codec,p)
        check(generated==out.raw,'Python LUT calculation exactly matches actual C including signed division')
        check(generated[1215:]==base[1215:],'calibration property tail unchanged')
    for p in ([-10,0,0,0,0],[0,0,0,-1,0],[0,0,0,10,0],[0,0,0,0,10]):
        rejects(lambda:status.adjusted_lut(base,codec,p),'invalid control rejected')
    def preference(parameters,generation=5,enabled=1):
        table=status.adjusted_lut(base,codec,parameters[:5])
        item=Preference(generation,enabled,(ctypes.c_int*8)(*parameters),zlib.crc32(table))
        out=ctypes.create_string_buffer(128)
        check(lib.a7_fl_preference_encode(out,ctypes.byref(item),digest,build)==0,'actual C preference encoder succeeds')
        return out.raw
    params=[-2,3,-4,2,-1,0,3,0];pref=preference(params)
    parsed=status.decode_preference(pref,digest.hex())
    check(parsed['state']=='valid' and parsed['parameters']==params and parsed['generation']==5,'actual C preference encoded record decoded exactly')
    for n in range(128):check(status.decode_preference(pref[:n],digest.hex())['state']=='invalid','all truncated preference records rejected')
    for at in range(128):
        damaged=bytearray(pref);damaged[at]^=1
        check(status.decode_preference(bytes(damaged),digest.hex())['state']=='invalid','all single-byte preference corruption rejected')
    records=[pref,preference(params,generation=6),preference([0,0,0,0,0,0,3,0]),None,pref[:-1]]
    for a in records:
        for b in records:
            selected=status.select_preferences([a,b],digest.hex());out=Preference()
            native=lib.a7_fl_preference_choose(ctypes.byref(out),a,len(a or b''),b,len(b or b''),digest,build)
            check((selected['selected'] if selected['selected'] is not None else -2 if selected['state']=='conflicting' else -1)==native,
                  'two-slot selection matches actual C for valid/torn/absent/conflicting records')
    for offset,value in ((12,0),(20,2),(24,10),(36,10),(48,0),(116,1),(120,1)):
        damaged=bytearray(pref);struct.pack_into('<I',damaged,offset,value);struct.pack_into('<I',damaged,124,zlib.crc32(damaged[:124]));out=Preference()
        native=lib.a7_fl_preference_decode(ctypes.byref(out),bytes(damaged),128,digest,build)
        check(native!=0 and status.decode_preference(bytes(damaged),digest.hex())['state']=='invalid','valid-checksum invalid preference values rejected by Python and C')
    module=ELF(bundle.directory/'input0.bin');symbols={'bootstrap_symbol':module.symbols['a7_fl_bootstrap_status']['value'],'runtime_symbol':module.symbols['a7_fl_status']['value']}
    def report(mode=1,loaded=1,stable=1,installed=1,ready=1,dirty=0,parameters=params):
        header=struct.pack('<IIi4Ii3I',0x41374653,1,loaded,0x40000000,0x70000000,
                           0x70000000+symbols['bootstrap_symbol'],0x70000000+symbols['runtime_symbol'],0,36,68,stable)
        boot=struct.pack('<4Ii4I',1,2,0,3,0,1,0x40000000,0x50000000,0x60000000)
        runtime=struct.pack('<7I10i',1,installed,0,1,dirty,5,ready,0,mode,*parameters)
        return header+boot+runtime
    raw=report();decoded=status.decode_report(raw,symbols)
    check(decoded['state']=='resident-ready' and decoded['runtime']['parameters']==params and not decoded['cold_power_verified'],
          'loaded report decoded without pretending physical or cold boot validation')
    for n in range(148):rejects(lambda:status.decode_report(raw[:n],symbols),'truncated resident report rejected')
    rejects(lambda:status.decode_report(raw+b'x',symbols),'long report rejected')
    for offset,value in ((0,0),(4,2),(32,35),(36,67),(40,2),(20,0x70000100)):
        damaged=bytearray(raw);struct.pack_into('<I',damaged,offset,value)
        rejects(lambda:status.decode_report(bytes(damaged),symbols),'malformed header or foreign exported symbol rejected')
    check(status.decode_report(report(loaded=0),symbols)['state']=='not-loaded','absent resident module remains pending')
    check(status.decode_report(report(loaded=-3),symbols)['state']=='probe-error','probe failure is explicit')
    check(status.decode_report(report(stable=0),symbols)['state']=='unstable','unstable snapshot is explicit')
    check(status.decode_report(report(ready=0),symbols)['state']=='loaded-awaiting-initialization','loaded but inactive module is not ready')
    check(status.decode_report(report(installed=0),symbols)['state']=='color-ready-menu-pending','color initialization distinct from menu registration')
    damaged=bytearray(raw);struct.pack_into('<i',damaged,108,-7)
    check(status.decode_report(bytes(damaged),symbols)['state']=='module-reported-error','last native failure remains visible')
    profile=types.SimpleNamespace(original=originals,base=base,codec=codec,original_sha=digest.hex(),symbols=symbols,
                                  bundle=bundle,payload=b'mock-readonly-NOLOAD-probe')
    candidate=status.adjusted_lut(base,codec,params[:5]);tables=[candidate,*originals[1:]]
    result=status.observations(profile,decoded,[pref,None],tables)
    check(result['active_table_matches_runtime'] and result['other_three_tables_original'] and result['runtime_matches_saved_preferences'],
          'nonzero control LUT and saved settings verified exactly')
    off=status.observations(profile,status.decode_report(report(mode=0),symbols),[preference(params,enabled=0),None],originals)
    check(off['active_table_matches_runtime'] and off['runtime_matches_saved_preferences'],'Off verifies original table and saved mode')
    absent=status.observations(profile,status.decode_report(report(loaded=0),symbols),[None,None],tables)
    check(absent['active_table_matches_runtime'] is None and absent['runtime_matches_saved_preferences'] is None,
          'recognized table bytes alone never imply a loaded module')
    changed=list(tables);changed[3]=bytes([tables[3][0]^1])+tables[3][1:]
    check(not status.observations(profile,decoded,[pref,None],changed)['other_three_tables_original'],'unrelated calibration mutation detected')
    check(not status.observations(profile,decoded,[pref,None],originals)['active_table_matches_runtime'],'enabled but original table mismatch detected')
    result=status.observations(profile,status.decode_report(report(dirty=1),symbols),[pref,None],tables)
    check(result['active_table_matches_runtime'] and result['runtime_matches_saved_preferences'] is False,'unsaved preview distinguished from persisted setting')
    result=status.observations(profile,status.decode_report(report(stable=0),symbols),[pref,None],tables)
    check(result['active_table_matches_runtime'] is None and result['runtime_matches_saved_preferences'] is None,'unstable snapshot never yields positive runtime verification')
    class Factory:
        missing=(0,0x10000006)
        def __init__(self):self.calls=[]
        def contents(self,path):
            self.calls.append(('contents',path));return status.BUILD_ID if path=='/version.txt' else (bundle.directory/'input0.bin').read_bytes()
        def run(self,payload,name):
            self.calls.append(('run',name));check(payload==profile.payload and name=='a7status.bin','only attested NOLOAD probe invoked');return raw
        def read(self,path,maximum):
            self.calls.append(('read',path));check(maximum==160,'preference read bounded');return ((0,0),pref) if path==status.PREFERENCES[0] else (self.missing,b'')
    class Camera:
        def __init__(self):self.factory=Factory();self.reads=[]
        def readBackup(self,key):
            self.reads.append(key);return b'ILCE-7M3'+bytes(8) if key==0x3e0005 else tables[key-0x30004]
    service=types.ModuleType('camera.service');service.Factory=lambda camera:camera.factory
    with patch.dict(sys.modules,{'camera.service':service}):
        camera=Camera()
        with tempfile.TemporaryDirectory(dir=OUT) as folder:
            result=status.inspect_camera(camera,profile,Path(folder))
        check(result['observations']['runtime_matches_saved_preferences'] and result['persistent_device_writes'] is False,
              'mock live read-only workflow decodes and verifies all inputs')
        check(camera.reads==[0x3e0005,0x30004,0x30005,0x30006,0x30007],'only model and four LUT read APIs called')
        camera=Camera()
        with tempfile.TemporaryDirectory(dir=OUT) as folder:
            result=status.inspect_camera(camera,profile,Path(folder),report_only=True)
        check(camera.reads==[0x3e0005] and 'observations' not in result and not any(c[0]=='read' for c in camera.factory.calls),
              'report-only workflow does not read preferences or calibration')
    (OUT/'resident-fixture.bin').write_bytes(raw)
    guard='''import builtins,json,sys
old=builtins.__import__
def safe(name,*args,**kwargs):
 if name.startswith(('usb','pmca')) or name in ('camera.service','camera.handoff'):
  raise RuntimeError('Offline operation imported camera transport: '+name)
 return old(name,*args,**kwargs)
builtins.__import__=safe
from camera import native_status
sys.argv=['native-status']+sys.argv[1:]
native_status.main()
assert not any(n.startswith(('usb','pmca')) or n in ('camera.service','camera.handoff') for n in sys.modules)
'''
    offline_outputs=[]
    for args in (['--offline'],['--decode',str(OUT/'resident-fixture.bin')]):
        run=subprocess.run([sys.executable,'-c',guard,*args],cwd=ROOT,check=True,capture_output=True,text=True)
        output=json.loads(run.stdout);check(output['camera_contacted'] is False,'actual offline/decode CLI never imports transport')
        offline_outputs.append(output)
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources=['camera/native_status.py','research/native_status_test.py','camera/native_install.py','payloads/a7-fl-color.h',
             'payloads/a7-fl-runtime.c','payloads/a7-fl-runtime-prefs.c','payloads/a7-fl-runtime-prefs.h','payloads/a7-fl-runtime.h']
    proof={'source_sha256':{p:h(ROOT/p) for p in sources},'checks':checks,'color_cases':len(cases),
           'module_sha256':bundle.files[0]['sha256'],'camera_contacted':False,
           'probe_proof_sha256':h(ROOT/'.lab/native-inspect/proof.json'),
           'bundle_manifest_sha256':h(bundle.manifest_path),'offline_outputs':offline_outputs,
           'scope':'Actual C LUT generator and preference codec compared with host decoder; report corruption and mocked read-only Factory workflow. No USB or live camera writes.'}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('NATIVE_STATUS_CHECKS',checks,'COLOR_CASES',len(cases));print('NATIVE_STATUS_TESTS_PASSED')

if __name__=='__main__':main()
