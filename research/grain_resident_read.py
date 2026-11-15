#!/usr/bin/env python3
"""Read-only r15 cold-boot inspection; never load/rearm the grain kernel."""
import argparse,ctypes as C,hashlib,json,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera import native_status
from research.capture_source_fetch import SOURCE

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binding',type=Path,required=True);p.add_argument('--probe',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
 profile=native_status.Profile(ROOT/'.lab/native-install-bound',a.binding.resolve()/'module-proof.json',a.probe.resolve(),ROOT/'.lab/native-fl-01',replacement_binding=a.binding.resolve(),capture_proof=ROOT/'.lab/lut3d-fl2-reference-private/proof.json')
 out=ROOT/'.lab/grain-resident-read'/str(time.time_ns());out.mkdir(parents=True)
 source=r'''
static struct{int report_n,selection_n,uptime_n;char report[4096],selection[32],uptime[64];} r;
static long sc(long n,long a,long b,long c){register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;__asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;}
static int readfile(const char*p,char*b,unsigned cap){long fd=sc(5,(long)p,0,0);if(fd<0)return fd;unsigned pos=0;while(pos<cap){long n=sc(3,fd,(long)(b+pos),cap-pos);if(n<0){sc(6,fd,0,0);return n;}if(!n)break;pos+=n;}long c=sc(6,fd,0,0);return c?c:(int)pos;}
__attribute__((constructor))static void run(void){r.report_n=readfile("/sys/module/a7capbanks/parameters/report",r.report,sizeof r.report);r.selection_n=readfile("/sys/module/a7capbanks/parameters/selection",r.selection,sizeof r.selection);r.uptime_n=readfile("/proc/uptime",r.uptime,sizeof r.uptime);long fd=sc(5,(long)"/tmp/jiritsu/a7gc.bin",1|64|128,0600);if(fd<0)return;long n=sc(4,fd,(long)&r,sizeof r),c=sc(6,fd,0,0);if(n!=sizeof r||c)sc(10,(long)"/tmp/jiritsu/a7gc.bin",0,0);}
'''
 (out/'kernel-read.c').write_text(source)
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror',str(out/'kernel-read.c'),'-o',str(out/'kernel-read.so')],check=True)
 (out/'decode.c').write_text('''#include "a7-fl-runtime-prefs.h"
int summarize(const uint8_t *a,const uint8_t*b,const uint8_t*h,const char*build,int*out){struct a7_fl_preference p;int r=a7_fl_preference_choose(&p,a,128,b,128,h,build);if(r<0)return r;out[0]=r;out[1]=p.schema;out[2]=p.generation;out[3]=p.enabled;for(unsigned bank=0;bank<3;bank++)for(unsigned f=0;f<7;f++)out[4+bank*7+f]=p.film[bank][f];for(unsigned f=0;f<8;f++)out[25+f]=p.parameters[f];return 0;}
''')
 subprocess.run(['clang','-dynamiclib','-O2','-DA7_FL_FILM_CONTROLS','-DA7_FL_DUAL_LOOK','-DA7_FL_LEICA_LOOK','-DA7_FL_LOOK_BANKS','-I'+str(ROOT/'payloads'),str(out/'decode.c'),str(ROOT/'payloads/a7-fl-runtime-prefs.c'),str(ROOT/'payloads/a7-fl-runtime.c'),'-o',str(out/'decode.dylib')],check=True)
 decode=C.CDLL(str(out/'decode.dylib')).summarize;decode.argtypes=[C.c_char_p]*4+[C.POINTER(C.c_int)];decode.restype=C.c_int
 def decode_slots(slots):
  result=(C.c_int*33)();digest=hashlib.sha256((ROOT/'.lab/native-fl-01/00030004.bin').read_bytes()).digest();build=b'37114_13.2026020901'.ljust(24,b'\0')
  if any(len(s)!=128 for s in slots) or decode(*slots,digest,build,result):raise ValueError('No verified saved preference')
  v=list(result);return dict(slot=v[0],schema=v[1],generation=v[2],mode=v[3],film=[v[4+i*7:11+i*7] for i in range(3)],parameters=v[25:33])
 # Exercise exact compiled decoder on the retained known-valid pre-update slots.
 baseline=ROOT/'.lab/native-fl-releases/update-r15-grain-tyoj7ine/write-1794714164598707000'
 decode_slots([(baseline/f'preference-before-{i}.bin').read_bytes() for i in range(2)])
 if not a.live:print('GRAIN_RESIDENT_READER_PREPARED',out);return
 from camera import handoff,service
 def collect(camera,action):
  if action!='settings-snapshot':raise ValueError('Unexpected action')
  result=native_status.inspect_camera(camera,profile,out,True)
  f=service.Factory(camera);raw=f.run((out/'kernel-read.so').read_bytes(),'a7gc.bin');(out/'kernel-read.bin').write_bytes(raw)
  if len(raw)!=4204:raise ValueError('Wrong kernel report length')
  rn,sn,un=struct.unpack_from('<3i',raw);kernel=dict(read_status=[rn,sn,un])
  if 0<rn<4096 and 0<sn<32 and 0<un<64:
   vals=list(map(int,raw[12:12+rn].decode().strip().split(',')));selection=int(raw[4108:4108+sn].decode().strip())
   kp=json.loads((ROOT/'.lab/capture-kernel/1794713346566010000/proof.json').read_text())
   if len(vals)!=368 or vals[0]!=0x4137434b or vals[12:16]!=kp['source_id']:raise ValueError('Wrong booted kernel identity')
   kernel.update(armed=bool(vals[1] and vals[11] and not vals[5]),selection=selection,completed=vals[355],failed=vals[357],uptime=raw[4140:4140+un].decode().strip())
  slots=[f.contents('/setting/A7FL%d.CFG'%i,maximum=160) for i in range(2)]
  for i,slot in enumerate(slots):(out/f'preference-{i}.bin').write_bytes(slot)
  saved=decode_slots(slots);desired=(saved['mode']<<4)|saved['film'][saved['mode']-1][0] if saved['mode'] else 0
  result.update(grain_kernel=kernel,saved=saved,kernel_matches_saved=bool(kernel.get('armed') and kernel.get('selection')==desired),persistent_device_writes=False)
  (out/'grain-status.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print('EVIDENCE',out)
 old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
 try:handoff.run('settings-snapshot')
 finally:service.perform=old;handoff.SWITCH=sw
if __name__=='__main__':main()
