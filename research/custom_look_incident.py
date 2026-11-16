"""Read-only independent-look crash collection; no persistent camera writes."""
import sys,time,json,subprocess,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.sd_import_acceptance import SOURCE
from camera import service,handoff
from local import LAB,BUILD_ID,require
s=SOURCE.replace('char uptime[64];','char uptime[64];int log_size;char log[32768];').replace('fd=sc(5,(long)"/tmp/jiritsu/sdaccept.bin"','report.log_size=sc(103,3,(long)report.log,sizeof report.log);\n fd=sc(5,(long)"/tmp/jiritsu/sdaccept.bin"')
out=LAB/'custom-look-incident'/str(time.time_ns());out.mkdir(parents=True)
(out/'read.c').write_text(s)
subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-nostdlib','-shared',str(out/'read.c'),'-o',str(out/'read.so')],check=True)
def collect(camera,action):
 f=service.Factory(camera);require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong camera')
 for name in ['A7CU0.CFG','A7CU1.CFG','A7FL0.CFG','A7FL1.CFG','A7FW0.CFG','A7FW1.CFG']:
  status,raw=f.read('/setting/'+name,maximum=4096)
  (out/(name+'.status')).write_text(str(status))
  if status==(0,0):(out/name).write_bytes(raw)
 raw=f.contents('/usr/lib/a7fl.so',maximum=200000);(out/'module.so').write_bytes(raw)
 report=f.run((out/'read.so').read_bytes(),'sdaccept.bin');(out/'runtime.bin').write_bytes(report)
 require(len(report)==32912,'Wrong report length')
 v=struct.unpack_from('<19i',report);n=struct.unpack_from('<i',report,140)[0]
 (out/'kernel.log').write_bytes(report[144:144+max(0,n)])
 result=dict(module_sha256=hashlib.sha256(raw).hexdigest(),valid=v[1],status=list(v[2:]),uptime=report[76:140].split(b'\0')[0].decode(),log_size=n,persistent_writes=False)
 (out/'readback.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);print('INCIDENT',out,flush=True)
service.perform=collect;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
