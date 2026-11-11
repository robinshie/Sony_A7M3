#!/usr/bin/env python3
"""Mock transport workflow regression; never imports the USB transport."""
import hashlib,json,struct,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera import native_module_replace as host
from local import BUILD_ID
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binding',type=Path,default=ROOT/'.lab/native-module-replace-bound-r1');args=parser.parse_args()
B=args.binding.resolve();bundle=host.Bundle(B);m=bundle.manifest
old=(B/'old-module.so').read_bytes();new=(B/'new-module.so').read_bytes();view=(ROOT/'.lab/native-setting-loader/viewUnified2.so').read_bytes()
checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:raise AssertionError(label)
class Env:
 def __init__(self):self.disk=old;self.backup=None;self.log=None;self.writes=0;self.preflights=0;self.fail_preflight=False;self.fail_write=False;self.fail_readback=False;self.model=b'ILCE-7M3'+bytes(8);self.wbi_zero=True;self.journal_bad=False
 def readBackup(self,key):check(key==0x3e0005,'model-only host backup read');return self.model
def report(env,write):
 status=-3 if (env.fail_write if write else env.fail_preflight) else 0
 return struct.pack('<6I4i32s',0x41374652,1,100 if write else 1,0,int(write),int(write),status,0,0,1,bytes.fromhex(m['bundle_sha256']))
def journal():
 out=b''
 for seq,(phase,created,backed,published) in enumerate(host.FORWARD,1):
  row=struct.pack('<6I',0x41374655,seq,phase,created,backed,published)+bytes.fromhex(m['bundle_sha256']);out+=row+hashlib.sha256(row).digest()
 return out
class Factory:
 missing=(0,0x10000006)
 def __init__(self,camera):self.e=camera
 def contents(self,path,maximum=1048576):
  if path=='/version.txt':return BUILD_ID
  st,data=self.read(path,maximum);check(st==(0,0),'existing mock contents');return data
 def read(self,path,maximum=1048576):
  values={host.MODULE:self.e.disk,host.VIEW:view,bundle.backup:self.e.backup,bundle.journal:self.e.log,bundle.temporary:None}
  check(path in values,'bounded file read path');v=values[path]
  if v is None:return self.missing,b''
  check(len(v)<=maximum,'bounded read size');return (0,0),v
 def run(self,payload,name):
  check(name=='a7modup.bin','expected report path')
  if payload==bundle.payloads['preflight']:self.e.preflights+=1;return report(self.e,False)
  check(payload==bundle.payloads['replace'],'expected exact writer')
  self.e.writes+=1;check(self.e.preflights==1,'same-session preflight precedes writer')
  self.e.backup=old;self.e.disk=(new[:-1]+bytes([new[-1]^1])) if self.e.fail_readback else new;self.e.log=journal()
  if self.e.journal_bad:self.e.log=self.e.log[:-1]
  return report(self.e,True)
def capture(camera,e):
 e.mkdir();(e/'header.bin').write_bytes(bytes(512) if camera.wbi_zero else b'WBI1'+bytes(508));(e/'neighbor.bin').write_bytes(b'N'*512)
 return dict(status=1 if camera.wbi_zero else 0,phase=2,header_kind=0,error=0,capacity_lo=62914560,capacity_hi=0)
sys.modules['camera.service']=SimpleNamespace(Factory=Factory);host.capture=capture
with tempfile.TemporaryDirectory(dir=B) as temp:
 root=Path(temp)
 def run(env,name,write=False,operation='replace'):
  return host.operate(env,bundle,operation,root/name,write)
 def reject(env,name,write=False):
  try:run(env,name,write)
  except ValueError:return
  raise AssertionError('guard bypassed: '+name)
 env=Env();reject(env,'no-write-flag');check(not env.writes,'no flag sends no writer')
 env=Env();r=run(env,'preflight',operation='preflight');check(r['verified'] and not env.writes and env.preflights==1,'default read-only preflight')
 env=Env();r=run(env,'good',True);check(r['verified'] and env.writes==1,'successful single replacement')
 check((root/'good/old-module.so').read_bytes()==old and (root/'good/new-module-readback.so').read_bytes()==new,'full old/new evidence')
 check((root/'good/write-intent.json').exists() and (root/'good/device-journal.json').exists(),'intent and exact journal retained')
 for name,field,value in [('model','model',b'OTHER'+bytes(11)),('wbi','wbi_zero',False),('preflight-fail','fail_preflight',True),('existing-journal','log',b'old')]:
  env=Env();setattr(env,field,value);reject(env,name,True);check(env.writes==0,'guard sends no writer: '+name)
 for name,field in [('writer-failure','fail_write'),('readback-failure','fail_readback'),('torn-journal','journal_bad')]:
  env=Env();setattr(env,field,True);reject(env,name,True);check(env.writes==1,'failure never retries: '+name);check(not(root/name/'verified.json').exists(),'failure not declared success: '+name)
  check((root/name/'replace-report.bin').exists(),'failure report retained: '+name)
 raw=journal();check(host.journal(raw,m['bundle_sha256'])['complete'],'exact forward journal accepted')
 changed=bytearray(raw);changed[88+4:88+8]=struct.pack('<I',99);check(not host.journal(bytes(changed),m['bundle_sha256'])['complete'],'sequence/hash tamper rejected')
proof={'result':'NMR_HOST_ALL_PASS','checks':checks,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'camera/native_module_replace.py']},'manifest_sha256':hashlib.sha256((B/'manifest.json').read_bytes()).hexdigest(),'camera_contacted':False,'scope':'Host model/WBI/preflight/explicit-write guards; full file readback; exact journal; no retry after write, journal or readback failure. Transport and device filesystem are mocked.'}
(B/'host-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
