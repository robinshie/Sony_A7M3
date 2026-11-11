#!/usr/bin/env python3
"""Sample at most 256 bytes per observed buffer. No writes or ownership claim.

The descriptor may be stale. This diagnostic cannot authorize pixel processing.
Offline by default; --live uses the guarded maintenance identity check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.yc_trace import PINS,require

def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trace',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
 trace=json.loads(a.trace.read_text());require(trace['status']==2 and trace['armed']==0 and trace['kind']==3 and trace['count']==1,'Expected one detached StillInfo observation')
 descriptor=bytes.fromhex(trace['records'][0]['raw']);require(len(descriptor)==3400,'Wrong descriptor length')
 areas=[struct.unpack_from('<2I',descriptor,8+i*16) for i in range(12)]
 out=ROOT/'.lab/still-buffer-snapshot'/str(time.time_ns());out.mkdir(parents=True)
 (out/'still-buffer-pins.h').write_text('static const unsigned sample_areas[12][2]={'+','.join('{'+str(x)+','+str(y)+'}' for x,y in areas)+'};\n')
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Wno-unused-function','-Wno-misleading-indentation','-I',str(ROOT/'payloads'),'-I',str(out),str(ROOT/'research/still_buffer_snapshot.c'),'-o',str(out/'snapshot.so')],check=True)
 (out/'proof.json').write_text(json.dumps(dict(trace_sha256=sha(a.trace.read_bytes()),descriptor_sha256=sha(descriptor),payload_sha256=sha((out/'snapshot.so').read_bytes()),source_sha256={s:sha((ROOT/s).read_bytes()) for s in ('research/still_buffer_snapshot.c','research/still_buffer_snapshot.py','payloads/a7-runtime-probe.c')},scope='Read-only bounded samples of possibly stale mapped addresses; no image ownership established'),indent=2)+'\n')
 if a.live:
  from camera import handoff,service
  def collect(camera,action):
   f=service.Factory(camera)
   require(f.contents('/version.txt')==b'37114_13.2026020901' and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model/build')
   for name in ('libObj.so','libmpr.so'):require(sha(f.contents('/usr/lib/'+name,32*1024*1024))==PINS[name],'Wrong library '+name)
   raw=f.run((out/'snapshot.so').read_bytes(),'a7sb.bin');(out/'live.bin').write_bytes(raw)
   require(len(raw)==3328 and struct.unpack_from('<IIiI',raw)==(0x41375342,1,1,12),'Snapshot rejected')
   rows=[]
   for i in range(12):
    at=16+i*276;offset,address,length,status,copied=struct.unpack_from('<IIIiI',raw,at)
    require((address,length)==areas[i] and offset==8+16*i and copied<=min(256,length),'Unexpected sample identity/length')
    data=raw[at+20:at+20+copied];rows.append(dict(offset=hex(offset),address=hex(address),length=length,status=status,copied=copied,sample=data.hex()))
    print('BUFFER_SAMPLE',hex(offset),'status',status,'length',length,'first16',data[:16].hex())
   (out/'live.json').write_text(json.dumps(dict(samples=rows,ownership_verified=False,photograph_identity_verified=False),indent=2)+'\n')
  service.perform=collect;previous=handoff.SWITCH;handoff.SWITCH+=' --host-identity-check'
  try:handoff.run('settings-snapshot')
  finally:handoff.SWITCH=previous
 print('EVIDENCE',out)
if __name__=='__main__':main()
