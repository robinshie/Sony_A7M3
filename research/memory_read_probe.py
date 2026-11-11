#!/usr/bin/env python3
"""Verify self-memory read availability; no foreign buffers, hooks or firmware writes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.yc_trace import require
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');a=p.parse_args()
 out=ROOT/'.lab/memory-read-probe'/str(time.time_ns());out.mkdir(parents=True)
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Wno-unused-function','-I',str(ROOT/'payloads'),str(ROOT/'research/memory_read_probe.c'),'-o',str(out/'probe.so')],check=True)
 (out/'proof.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('research/memory_read_probe.c','research/memory_read_probe.py','payloads/a7-runtime-probe.c')},indent=2)+'\n')
 if a.live:
  from camera import handoff,service
  def collect(camera,action):
   f=service.Factory(camera)
   require(f.contents('/version.txt')==b'37114_13.2026020901' and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model/build')
   raw=f.run((out/'probe.so').read_bytes(),'a7mr.bin');(out/'live.bin').write_bytes(raw)
   require(len(raw)==2348,'Unexpected report size');h=struct.unpack_from('<2I5i2I2i',raw);require(h[:2]==(0x41374d52,1),'Wrong report version')
   result=dict(zip(('vm_read','vm_invalid','mem_open','mem_read','mem_invalid','vm_matches','mem_matches','kernel_length','meminfo_length'),h[2:]))
   for name,at,size in (('kernel',44,256),('meminfo',300,2048)):
    n=result[name+'_length'];result[name]=raw[at:at+max(0,min(n,size))].decode('utf8','replace')
   (out/'live.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
  service.perform=collect;previous=handoff.SWITCH;handoff.SWITCH+=' --host-identity-check'
  try:handoff.run('settings-snapshot')
  finally:handoff.SWITCH=previous
 print('EVIDENCE',out)
if __name__=='__main__':main()
