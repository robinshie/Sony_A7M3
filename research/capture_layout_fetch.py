#!/usr/bin/env python3
"""Disarm and fetch immutable native resize-task snapshots; never access image pixels."""
import argparse
import json
import struct
import subprocess
import time
from pathlib import Path
from kernel_probe import ROOT, sha

SOURCE=r'''
static struct { int status,n[8]; char text[7][4096],count[32]; } r;
static long sc(long n,long a,long b,long c) {
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc"); return r0;
}
static int readfile(const char*p,char*b,unsigned cap) {
 long fd=sc(5,(long)p,0,0);if(fd<0)return fd;unsigned pos=0;long n;
 while(pos<cap) {n=sc(3,fd,(long)(b+pos),cap-pos);if(n<=0)break;pos+=n;}
 long c=sc(6,fd,0,0);return n<0?n:c?c:(int)pos;
}
__attribute__((constructor))static void run(void) {
 static const char *paths[]={
 "/sys/module/a7caplayout/parameters/report",
 "/sys/module/a7caplayout/parameters/geometry0",
 "/sys/module/a7caplayout/parameters/geometry1",
 "/sys/module/a7caplayout/parameters/geometry2",
 "/sys/module/a7caplayout/parameters/layout0",
 "/sys/module/a7caplayout/parameters/layout1",
 "/sys/module/a7caplayout/parameters/layout2"};
 r.status=1;
 long fd=sc(5,(long)"/sys/module/a7caplayout/parameters/disarm",1,0);
 if(fd<0)goto output;
 long n=sc(4,fd,(long)"1",1),c=sc(6,fd,0,0);if(n!=1||c)goto output;
 r.status=0;
 for(unsigned i=0;i<7;i++)r.n[i]=readfile(paths[i],r.text[i],4096);
 r.n[7]=readfile("/sys/module/a7caplayout/parameters/geometry_captured",r.count,32);
 output:;
 fd=sc(5,(long)"/tmp/jiritsu/a7ly.bin",1|64|128,0600);if(fd<0)return;
 unsigned pos=0;while(pos<sizeof r){n=sc(4,fd,(long)((char*)&r+pos),sizeof r-pos);if(n<=0)break;pos+=n;}
 c=sc(6,fd,0,0);if(pos!=sizeof r||c)sc(10,(long)"/tmp/jiritsu/a7ly.bin",0,0);
}
'''

def decode(raw,identity,sizes=('M','S')):
    if len(raw)!=28740:raise ValueError('Wrong layout result length')
    status,*lengths=struct.unpack_from('<9i',raw)
    if status or any(n<=0 or n>=cap for n,cap in zip(lengths,[4096]*7+[32])):
        raise ValueError('Incomplete/disarm-failed layout read '+str((status,lengths)))
    parts=[raw[pos:pos+n].decode().strip() for pos,n in zip([36+i*4096 for i in range(7)]+[28708],lengths)]
    if int(parts[7])!=len(sizes):raise ValueError('Capture count differs from requested shot order: '+parts[7])
    words=[list(map(int,p.split(','))) for p in parts[:7]]
    for v in [words[0]]+words[1:1+len(sizes)]:
        if len(v)!=368 or v[0]!=0x4137434b or v[12:16]!=identity or any(x<0 or x>0xffffffff for x in v):
            raise ValueError('Wrong layout source identity')
    if words[0][5]!=1:raise ValueError('Callback not disarmed')
    out=[]
    for i,size in enumerate(sizes):
        v,l=words[i+1],words[i+4]
        if v[16]!=i+1 or v[17]!=3 or v[18] or v[224:256]!=v[272:304]:
            raise ValueError('Incomplete source metadata '+str(i))
        if len(l)!=352 or l[:4]!=[0x41374c59,1,0,i+1]:
            raise ValueError('Incomplete resize plan '+str((i,l[:4])))
        if (l[4]!=v[30] or l[5]!=l[12] or l[6]!=l[138] or l[7]!=l[136]):
            raise ValueError('Inconsistent resize pointer chain')
        out.append(dict(requested_size=size,encoder_object=v[40:172],source_record=v,
            task=l[8:136],info=l[136:152],input_plan=l[152:248],output_plan=l[248:280],
            encoder_extension=l[280:344],layout_record=l))
    return dict(observations=out,firmware_written=False,pixel_write=False,disarmed=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--live',action='store_true')
    p.add_argument('--sizes',nargs='+',choices=['L','M','S'],default=['M','S'])
    a=p.parse_args();proof=json.loads((a.bundle/'proof.json').read_text())
    if proof['route']!='layout' or sha((a.bundle/'a7caplayout.ko').read_bytes())!=proof['module_sha256']:
        raise ValueError('Wrong geometry bundle')
    out=ROOT/'.lab/capture-layout-read'/str(time.time_ns());out.mkdir(parents=True)
    (out/'read.c').write_text(SOURCE)
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft',
        '-fPIC','-Os','-ffreestanding','-fno-builtin','-nostdlib','-shared',
        '-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror',
        str(out/'read.c'),'-o',str(out/'read.so')],check=True)
    if a.live:
        from camera import handoff,service
        def collect(camera,action):
            if action!='settings-snapshot':raise ValueError('Unexpected action')
            f=service.Factory(camera)
            if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):
                raise ValueError('Wrong model/build')
            raw=f.run((out/'read.so').read_bytes(),'a7ly.bin');(out/'raw.bin').write_bytes(raw)
            result=decode(raw,proof['source_id'],tuple(a.sizes))
            result.update(bundle=str(a.bundle.resolve()),module_sha256=proof['module_sha256'])
            (out/'layout.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps([{k:v for k,v in o.items() if k not in ('source_record','layout_record','encoder_object','task','info','encoder_extension')}
                              for o in result['observations']],indent=2))
        old,sw=service.perform,handoff.SWITCH
        service.perform=collect;handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:service.perform, handoff.SWITCH=old,sw
    print('EVIDENCE',out)

if __name__=='__main__':main()
