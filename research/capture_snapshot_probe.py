#!/usr/bin/env python3
"""Read bounded current metadata at addresses evidenced by a capture trace.

Not an in-call sample: transient stack buffers are explicitly excluded.
"""
import argparse,json,struct,subprocess,sys,time
from pathlib import Path
from kernel_probe import ROOT,sha,PINS
sys.path.insert(0,str(ROOT))
SOURCE=r'''
#include <stdint.h>
#include "regions.h"
static struct {uint32_t magic,version;int32_t status[4];unsigned char data[1728];} report;
static long sc(long n,long a,long b,long c){
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static long read_phys(long fd,void *buf,unsigned size,unsigned address){
 register long r7 __asm__("r7")=180,r0 __asm__("r0")=fd,r1 __asm__("r1")=(long)buf;
 register long r2 __asm__("r2")=size,r3 __asm__("r3")=0,r4 __asm__("r4")=address,r5 __asm__("r5")=0;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
__attribute__((constructor)) static void run(void){
 report.magic=0x41374d44;report.version=1;
 long fd=sc(5,(long)"/dev/mem",0x1000,0);unsigned pos=0;
 for(unsigned i=0;i<4;i++){
  unsigned va=regions[i][0],size=regions[i][1];
  if(va<0x60000000 || va>0x80000000-size || pos>sizeof(report.data)-size){report.status[i]=-22;break;}
  report.status[i]=fd<0?fd:read_phys(fd,report.data+pos,size,va-0x60000000);pos+=size;
 }
 if(fd>=0)sc(6,fd,0,0);
 fd=sc(5,(long)"/tmp/jiritsu/a7md.bin",1|64|128,0600);if(fd<0)return;
 long n=sc(4,fd,(long)&report,sizeof report),c=sc(6,fd,0,0);
 if(n!=sizeof report||c)sc(10,(long)"/tmp/jiritsu/a7md.bin",0,0);
}
'''
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace',type=Path,required=True);p.add_argument('--avcam',type=Path,required=True)
    p.add_argument('--live',action='store_true');a=p.parse_args()
    av=a.avcam.read_bytes()
    if sha(av)!=PINS['avcam']:raise ValueError('Wrong original AV-CAM')
    trace=json.loads((a.trace/'proof.json').read_text())
    runs=[x for x in trace['live'] if x['action']=='collect' and x['verified']]
    if trace.get('route')!='multi' or not runs:raise ValueError('Needs verified multi-candidate capture')
    v=runs[-1]['values'];ctx=v[20];obj=v[80]
    if not (v[16] and v[76] and 0x635c6000<=obj<0x64700000 and 0x60000000<=ctx<0x7fff8000):
        raise ValueError('Unexpected stable metadata addresses')
    # Capture selector GOT slot and its fixed original table allocation.
    slot=0x647538b4+struct.unpack_from('<I',av,0x3358b8)[0]
    table=struct.unpack_from('<I',av,slot-0x635c6000)[0]
    regions=[(slot,4),(table,380),(obj,1280),(ctx+0x6750,64)]
    if sum(n for _,n in regions)!=1728:raise ValueError('Invalid bounded report')
    out=ROOT/'.lab/capture-metadata'/str(time.time_ns());out.mkdir(parents=True)
    (out/'probe.c').write_text(SOURCE)
    (out/'regions.h').write_text('static const unsigned regions[4][2]={'+','.join('{'+hex(x)+','+str(n)+'}' for x,n in regions)+'};\n')
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
        '-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack',
        '-Wall','-Wextra','-Werror','probe.c','-o','probe.so'],cwd=out,check=True)
    proof=dict(trace_sha256=sha((a.trace/'proof.json').read_bytes()),source_sha256=sha(Path(__file__).read_bytes()),
        payload_sha256=sha((out/'probe.so').read_bytes()),regions=regions,current_metadata_only=True,
        transient_stack_read=False,camera_run=False,pixel_write=False,firmware_written=False)
    if a.live:
        from camera import handoff,service
        def collect(camera,action):
            if action!='settings-snapshot':raise ValueError('Unexpected action')
            f=service.Factory(camera)
            if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong model/build')
            raw=f.run((out/'probe.so').read_bytes(),'a7md.bin');(out/'live.bin').write_bytes(raw)
            if len(raw)!=1752 or struct.unpack_from('<II',raw)!=(0x41374d44,1):raise ValueError('Wrong report')
            status=struct.unpack_from('<4i',raw,8)
            if status!=tuple(n for _,n in regions):raise ValueError('Incomplete metadata reads: '+str(status))
            pos=24
            for name,(_,n) in zip(('table_pointer','selector_table','encoder_object','geometry'),regions):
                (out/(name+'.bin')).write_bytes(raw[pos:pos+n]);pos+=n
            if struct.unpack_from('<I',raw,24)[0]!=table:raise ValueError('Runtime table pointer changed')
            proof.update(camera_run=True,temporary_files_removed=True,status=status)
            print('BOUNDED_CURRENT_METADATA_READ',status)
        old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:service.perform=old;handoff.SWITCH=sw
    (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('EVIDENCE',out)
if __name__=='__main__':main()
