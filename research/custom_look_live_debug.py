"""Read-only independent-look crash collection; no persistent camera writes."""
import sys,time,json,subprocess,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.sd_import_acceptance import SOURCE
from camera import service,handoff
from local import LAB,BUILD_ID,require
s='#include "a7-fl-custom-session.h"\n'+SOURCE
s=s.replace('char uptime[64];','char uptime[64];int details[16];char recipe[384];char paths[520];')
s=s.replace('dlclose(h);}', 'uintptr_t base=(uintptr_t)get-0x4734;\n const struct a7_custom_session*c=(void*)(base+0xbdc68);\n int v[16]={c->ready,c->dirty,c->fault,c->saved.generation,c->saved.count,c->saved.active,c->working.count,c->store.ready,c->store.selected,c->store.sizes[0],c->store.sizes[1],*(int*)(base+0x20e78),*(int*)(base+0x20e4c),*(int*)(base+0xd2604+40),*(int*)(base+0xd2604+48),0};\n for(unsigned i=0;i<16;i++)report.details[i]=v[i];\n for(unsigned i=0;i<384;i++)report.recipe[i]=*(char*)(base+0xb5b20+i);\n report.details[15]=*(int*)(base+0xbbbc4);\n for(unsigned i=0;i<520;i++)report.paths[i]=*(char*)(base+0xbbbc4+4+i);\n dlclose(h);}')
out=LAB/'custom-look-debug'/str(time.time_ns());out.mkdir(parents=True)
(out/'read.c').write_text(s)
subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-DA7_FL_SIX_LOOKS','-DA7_FL_FILM_CONTROLS','-DA7_FL_CAPTURE_VIGNETTE','-DA7_FL_LOOK_BANKS','-DA7_FL_LEICA_LOOK','-DA7_FL_DUAL_LOOK','-I'+str(ROOT/'payloads'),'-fPIC','-Os','-nostdlib','-shared',str(out/'read.c'),'-o',str(out/'read.so')],check=True)
def collect(camera,action):
 f=service.Factory(camera);require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong camera')
 for name in ['A7CU0.CFG','A7CU1.CFG','A7FL0.CFG','A7FL1.CFG','A7FW0.CFG','A7FW1.CFG']:
  status,raw=f.read('/setting/'+name,maximum=4096)
  (out/(name+'.status')).write_text(str(status))
  if status==(0,0):(out/name).write_bytes(raw)
 raw=f.contents('/usr/lib/a7fl.so',maximum=200000);require(hashlib.sha256(raw).hexdigest()=='87e8f719baeeaf3e391c3607557037b4bdf28f984fa604707732a78230d90c8d','Exact debug layout mismatch');(out/'module.so').write_bytes(raw)
 report=f.run((out/'read.so').read_bytes(),'sdaccept.bin');(out/'runtime.bin').write_bytes(report)
 require(len(report)==1108,'Wrong report length')
 v=struct.unpack_from('<19i',report)
 result=dict(module_sha256=hashlib.sha256(raw).hexdigest(),status=list(v[2:]),details=list(struct.unpack_from('<16i',report,140)),paths=[report[588+i*260:848+i*260].split(b'\0')[0].decode(errors='replace') for i in range(2)],recipe=report[204:588].split(b'\0')[0].decode(errors='replace'),persistent_writes=False)
 (out/'readback.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);print('INCIDENT',out,flush=True)
service.perform=collect;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
