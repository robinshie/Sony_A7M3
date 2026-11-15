#!/usr/bin/env python3
"""Read a bounded current DRAM sample referenced by a verified capture trace.

Post-capture evidence only: this does not hold a frame lease or establish that
bytes still belong to the recorded photograph. Never changes image memory.
"""
import argparse,json,struct,subprocess,sys,time
from pathlib import Path
from kernel_probe import ROOT,sha
sys.path.insert(0,str(ROOT))
SOURCE=r'''
#include <stdint.h>
#include "sample-pins.h"
#define ROW 12160u
#define COUNT 64u
#define SMALL 1520u
static struct {uint32_t magic,version;int32_t status;uint32_t rows,base,stride,step,slice;int32_t reads[COUNT];uint32_t observed[10];unsigned char data[COUNT*SMALL];} report;
static unsigned char line[ROW];
static long sc(long nr,long a,long b,long c,long d,long e,long f){
 register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c,r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
static long call(long n,long a,long b,long c){return sc(n,a,b,c,0,0,0);}
static long read_at(long fd,void *out,unsigned size,unsigned physical){return sc(180,fd,(long)out,size,0,physical,0);}
static int expired(const uint32_t start[2]){
 uint32_t now[2];if(call(263,1,(long)now,0))return 1;
 if(now[0]<start[0])return 1;
 unsigned s=now[0]-start[0];return s>1||(s==1&&now[1]>=start[1]);
}
static int match(long fd,unsigned at){
 uint32_t b[3],g[2];
 if(read_at(fd,b,12,OBJECT+0xbc-0x60000000)!=12 || read_at(fd,g,8,OBJECT+0x90-0x60000000)!=8)return 0;
 for(unsigned i=0;i<3;i++)report.observed[at+i]=b[i];
 for(unsigned i=0;i<2;i++)report.observed[at+3+i]=g[i];
 /* Original converter reads only the count byte; upper 24 bits are not range identity. */
 return (b[0]&255)==1 && b[1]==BASE && b[2]==CAPACITY && g[0]==0x0fa01770 && g[1]==0x0fa017c0;
}
__attribute__((constructor)) static void run(void){
 report.magic=0x41375350;report.version=2;report.status=-1;
 report.base=BASE;report.stride=ROW;report.step=128;report.slice=SMALL;
 /* Restrict to the precise observed DRAM allocation; no MMIO, no stale stack. */
 if(BASE!=0x1a000000 || CAPACITY!=0x03000000 || OBJECT!=0x641b6f10)return;
 if((31u*128u+1u)*ROW+ROW>CAPACITY)return;
 uint32_t start[2];long fd=call(5,(long)"/dev/mem",0x1000,0);
 if(fd<0)goto output;
 if(!match(fd,0)){report.status=-2;goto close;}
 if(call(263,1,(long)start,0)){report.status=-3;goto close;}
 for(unsigned i=0;i<COUNT;i++){
  if(expired(start)){report.status=-4;goto close;}
  unsigned row=(i/2)*128+i%2;
  report.reads[i]=read_at(fd,line,ROW,BASE+row*ROW);
  if(report.reads[i]!=ROW){report.status=-5;goto close;}
  for(unsigned group=0;group<ROW/32;group++)for(unsigned j=0;j<4;j++)report.data[i*SMALL+group*4+j]=line[group*32+j];
  report.rows=i+1;
 }
 report.status=match(fd,5)?0:-6;
close:
 if(call(6,fd,0,0)&&!report.status)report.status=-7;
output:
 fd=call(5,(long)"/tmp/jiritsu/a7sp.bin",1|64|128,0600);if(fd<0)return;
 unsigned pos=0;while(pos<sizeof report){long n=call(4,fd,(long)((char *)&report+pos),sizeof report-pos);if(n<=0)break;pos+=n;}
 long c=call(6,fd,0,0);if(pos!=sizeof report||c)call(10,(long)"/tmp/jiritsu/a7sp.bin",0,0);
}
'''
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trace',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
    q=json.loads((a.trace/'proof.json').read_text());runs=[r for r in q['live'] if r['action']=='collect' and r['verified']]
    if q.get('route')!='vfx' or not runs:raise ValueError('Need verified VFX capture trace')
    v=runs[-1]['values'];obj=v[254];b=struct.pack('<100I',*v[260:360]);d,base,cap=struct.unpack_from('<3I',b,0xbc)
    if v[252]!=3 or v[256]!=0 or obj!=0x641b6f10 or (base,cap)!=(0x1a000000,0x3000000) or d&255!=1:raise ValueError('Unexpected source descriptor')
    out=ROOT/'.lab/capture-source'/str(time.time_ns());out.mkdir(parents=True)
    (out/'sample.c').write_text(SOURCE)
    (out/'sample-pins.h').write_text(f'#define OBJECT {obj:#x}u\n#define DESCRIPTOR {d:#x}u\n#define BASE {base:#x}u\n#define CAPACITY {cap:#x}u\n')
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror','sample.c','-o','sample.so'],cwd=out,check=True)
    proof=dict(source_sha256=sha(Path(__file__).read_bytes()),trace_sha256=sha((a.trace/runs[-1]['report_file']).read_bytes()),payload_sha256=sha((out/'sample.so').read_bytes()),
        camera_run=False,pixel_write=False,firmware_written=False,frame_lease=False,post_capture_current_dram=True,cache_sync_called=False,
        sampling=dict(source_stride=12160,source_row_indices=[(i//2)*128+i%2 for i in range(64)],byte_groups='keep bytes 0..3 of every 32-byte group',sample_row_bytes=1520))
    try:
        if a.live:
            from camera import handoff,service
            def collect(camera,action):
                if action!='settings-snapshot':raise ValueError('Unexpected action')
                f=service.Factory(camera)
                if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong model/build')
                raw=f.run((out/'sample.so').read_bytes(),'a7sp.bin');(out/'live.bin').write_bytes(raw)
                if len(raw)!=97608:raise ValueError('Wrong sample report size: '+str(len(raw)))
                magic,version,status,rows,b,st,step,sl=struct.unpack_from('<IIi5I',raw)
                proof.update(camera_run=True,temporary_files_removed=True,status=status,rows=rows,observed=[hex(x) for x in struct.unpack_from("<10I",raw,288)])
                if (magic,version,status,rows,b,st,step,sl)!=(0x41375350,2,0,64,base,12160,128,1520):raise ValueError('Incomplete sample: '+str((status,rows)))
                if struct.unpack_from('<64i',raw,32)!=(12160,)*64:raise ValueError('Incomplete DRAM read')
                data=raw[328:];(out/'sample.raw').write_bytes(data);proof['sample_sha256']=sha(data)
                print('POST_CAPTURE_SAMPLE_READ',len(data),flush=True)
            old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
            try:handoff.run('settings-snapshot')
            finally:service.perform=old;handoff.SWITCH=sw
    finally:
        (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('EVIDENCE',out,flush=True)
if __name__=='__main__':main()
