"""Offline mocked-transport guard tests; never imports actual USB transport."""
import hashlib,json,struct,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local import BUILD_ID
from camera import native_wbi_write as host
B=ROOT/'.lab/native-wbi-bound';_,original,writer=host.verify(B)
disk=original;attempts=0;failed=False
def report(mode):
 global disk,attempts
 pre=disk
 if mode:
  attempts+=1;disk=bytes(512)+disk[512:]
  phase,status,written,sync,kind=100,0,512,1,2
  if failed:phase,status,sync=4,-1,0
 else:
  zero=pre[:512]==bytes(512);phase,status,written,sync,kind=(2,1,0,0,0) if zero else (3,0,0,0,2)
 return struct.pack('<3I2i9I',0x57423741,1,phase,status,0,163,62914560,0,mode,kind,written,sync,1,0)+hashlib.sha256(pre).digest()+pre
class Factory:
 def __init__(self,c):pass
 def contents(self,p):assert p=='/version.txt';return BUILD_ID
 def run(self,p,r):assert isinstance(p,bytes) and r=='a7wbi.bin';return report(int(p==writer))
sys.modules['camera.service']=SimpleNamespace(Factory=Factory)
camera=SimpleNamespace(readBackup=lambda key:b'ILCE-7M3'+bytes(8))
with tempfile.TemporaryDirectory(dir=B) as tmp:
 base=Path(tmp)
 try:host.invalidate(camera,B,base/'no-permission')
 except Exception:pass
 else:raise AssertionError('write flag bypassed')
 assert attempts==0
 result=host.invalidate(camera,B,base/'good',True)
 assert result['verified'] and attempts==1 and disk==bytes(512)+original[512:]
 assert (base/'good/write-intent.json').exists() and (base/'good/expected-1024.bin').read_bytes()==original
 disk=bytearray(original);disk[46]^=1;disk=bytes(disk)
 try:host.invalidate(camera,B,base/'changed',True)
 except Exception:pass
 else:raise AssertionError('changed preimage bypassed')
 assert attempts==1 and not (base/'changed/write-intent.json').exists()
 disk=original;failed=True
 try:host.invalidate(camera,B,base/'failed',True)
 except Exception:pass
 else:raise AssertionError('failed write reported complete')
 assert attempts==2 and (base/'failed/write-report.bin').exists() and not (base/'failed/verified.json').exists()
 assert not (base/'failed/readback').exists()
proof={'result':'NWB_HOST_ALL_PASS','binding_manifest_sha256':hashlib.sha256((B/'manifest.json').read_bytes()).hexdigest(),'tests':['explicit write flag','fresh same-session exact preimage','fsynced intent/original backups','successful independent zero/neighbor readback','changed preimage sends no writer','write error retains report and never retries/undoes'],'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'camera_contacted':False}
(B/'host-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
