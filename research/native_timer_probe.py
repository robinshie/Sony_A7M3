#!/usr/bin/env python3
"""Read only the native timer owner pid and existing manager fields."""
import argparse,hashlib,json,struct,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from local import BUILD_ID

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');a=p.parse_args()
 out=R/'.lab/native-timer-probe'/str(time.time_ns());out.mkdir(parents=True)
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-fPIC','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-nostdlib','-shared','-Wl,--no-undefined,-z,noexecstack','-Wall','-Wextra','-Wno-unused-function','-Wno-misleading-indentation','-I',str(R/'payloads'),'-I',str(R/'.lab/native-preview-cycle'),str(R/'research/native_timer_probe.c'),'-o',str(out/'probe.so')],check=True)
 proof={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in ['research/native_timer_probe.c','research/native_timer_probe.py','payloads/a7-runtime-probe.c','.lab/native-preview-cycle/a7-fl-preview-cycle-pins.h']};(out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
 if a.live:
  from camera import handoff,service
  def collect(camera,action):
   f=service.Factory(camera)
   assert f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8)
   raw=f.run((out/'probe.so').read_bytes(),'a7timer.bin');(out/'live.bin').write_bytes(raw)
   assert len(raw)==60;v=struct.unpack('<15I',raw);assert v[0]==0x4137544d
   result=dict(pid=v[1],libobj_base=v[2],manager=v[3],status=v[4],manager_words=v[5:],timer_owner_pid=v[14],same_process=v[4]==2 and v[1]==v[14],persistent_writes=False)
   (out/'live.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
  service.perform=collect;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
 print('EVIDENCE',out,flush=True)
if __name__=='__main__':main()
