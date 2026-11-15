#!/usr/bin/env python3
"""Bind and optionally exercise the config bridge on an already-armed candidate."""
import argparse,hashlib,json,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
 b=a.bundle.resolve();proof=json.loads((b/'proof.json').read_text());name=proof['module_name']
 if proof['route']!='banks' or name!='a7capbanks':raise ValueError('Expected exact dual-bank repeat candidate')
 module=(b/(name+'.ko')).read_bytes()
 if sha(module)!=proof['module_sha256']:raise ValueError('Module identity differs')
 for n,h in proof['source_sha256'].items():
  if sha((ROOT/n).read_bytes())!=h:raise ValueError('Candidate sources changed: '+n)
 host=json.loads((ROOT/'.lab/grain-backend/proof.json').read_text())
 if not host['passed'] or any(sha((ROOT/n).read_bytes())!=h for n,h in host['source_sha256'].items()):raise ValueError('Run current host bridge test')
 out=ROOT/'.lab/grain-backend-live'/str(time.time_ns());out.mkdir(parents=True)
 (out/'kernel.ko').write_bytes(module)
 (out/'a7-fl-grain-kernel.h').write_text('#define A7_GRAIN_KERNEL_NAME "'+name+'"\nstatic const unsigned a7_grain_kernel_source_id[]={'+','.join(map(str,proof['source_id']))+'};\n')
 (out/'blob.S').write_text('.section .rodata\n.balign 4\n.global a7_grain_kernel_start,a7_grain_kernel_end\na7_grain_kernel_start:\n.incbin "kernel.ko"\na7_grain_kernel_end:\n.section .note.GNU-stack,"",%progbits\n')
 (out/'entry.c').write_text(r'''
#include "a7-fl-grain-backend.h"
static long sc(long n,long a,long b,long c){register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;__asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;}
static int r[5]={0x41374742,1,-9999,-9999,-9999};
__attribute__((constructor))static void run(void){
 long fd=sc(5,(long)"/sys/module/a7capbanks",0x4000,0);if(fd<0){r[2]=fd;goto output;}sc(6,fd,0,0);
 r[2]=a7_fl_grain_apply(3,9);if(!r[2])r[3]=a7_fl_grain_apply(0,0);
 r[4]=a7_fl_grain_apply(3,9);
output:fd=sc(5,(long)"/tmp/jiritsu/a7gbk.bin",1|64|128,0600);if(fd<0)return;
 long n=sc(4,fd,(long)r,sizeof r),c=sc(6,fd,0,0);if(n!=sizeof r||c)sc(10,(long)"/tmp/jiritsu/a7gbk.bin",0,0);
}
''')
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror','-I'+str(out),'-I'+str(ROOT/'payloads'),'entry.c',str(ROOT/'payloads/a7-fl-grain-backend.c'),'blob.S','-lgcc','-o','probe.so'],cwd=out,check=True)
 result=dict(kernel_bundle=str(b),kernel_sha256=sha(module),kernel_source_id=proof['source_id'],camera_run=False,firmware_written=False,source_sha256={n:sha((ROOT/n).read_bytes()) for n in ['research/grain_backend_live.py','payloads/a7-fl-grain-backend.c','payloads/a7-fl-grain-backend.h']},payload_sha256=sha((out/'probe.so').read_bytes()))
 if a.live:
  from camera import handoff,service
  def collect(camera,action):
   f=service.Factory(camera)
   if action!='settings-snapshot' or f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong model/build')
   raw=f.run((out/'probe.so').read_bytes(),'a7gbk.bin');(out/'live.bin').write_bytes(raw)
   if len(raw)!=20:raise ValueError('Wrong bridge report')
   values=struct.unpack('<5i',raw);result.update(camera_run=True,values=values,temporary_files_removed=True,passed=values==(0x41374742,1,0,0,0))
   (out/'proof.json').write_text(json.dumps(result,indent=2)+'\n')
   if not result['passed']:raise ValueError('Bridge result '+str(values))
   print('CAPTURE_GRAIN_BRIDGE_LIVE_PASSED')
  old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
  try:handoff.run('settings-snapshot')
  finally:service.perform=old;handoff.SWITCH=sw
 (out/'proof.json').write_text(json.dumps(result,indent=2)+'\n');print('EVIDENCE',out)
if __name__=='__main__':main()
