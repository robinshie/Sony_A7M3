#!/usr/bin/env python3
"""Disarm and fetch three immutable size snapshots; never access image pixels."""
import argparse
import json
import struct
import subprocess
import time
from pathlib import Path
from kernel_probe import ROOT, sha

SOURCE=r'''
static struct { int status,n[5]; char text[4][4096],count[32]; } r;
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
 "/sys/module/a7capgeom/parameters/report",
 "/sys/module/a7capgeom/parameters/geometry0",
 "/sys/module/a7capgeom/parameters/geometry1",
 "/sys/module/a7capgeom/parameters/geometry2"};
 r.status=1;
 long fd=sc(5,(long)"/sys/module/a7capgeom/parameters/disarm",1,0);
 if(fd<0)goto output;
 long n=sc(4,fd,(long)"1",1),c=sc(6,fd,0,0);if(n!=1||c)goto output;
 r.status=0;
 for(unsigned i=0;i<4;i++)r.n[i]=readfile(paths[i],r.text[i],4096);
 r.n[4]=readfile("/sys/module/a7capgeom/parameters/geometry_captured",r.count,32);
 output:;
 fd=sc(5,(long)"/tmp/jiritsu/a7gm.bin",1|64|128,0600);if(fd<0)return;
 unsigned pos=0;while(pos<sizeof r){n=sc(4,fd,(long)((char*)&r+pos),sizeof r-pos);if(n<=0)break;pos+=n;}
 c=sc(6,fd,0,0);if(pos!=sizeof r||c)sc(10,(long)"/tmp/jiritsu/a7gm.bin",0,0);
}
'''

def decode(raw,identity):
    if len(raw)!=16440: raise ValueError('Wrong geometry result length')
    status,*sizes=struct.unpack_from('<6i',raw)
    if status or any(n<=0 or n>=cap for n,cap in zip(sizes,[4096]*4+[32])):
        raise ValueError('Incomplete/disarm-failed geometry result: '+str((status,sizes)))
    parts=[raw[pos:pos+n].decode().strip() for pos,n in zip([24,4120,8216,12312,16408],sizes)]
    if int(parts[4])!=3: raise ValueError('Need three captures, received '+parts[4])
    values=[list(map(int,p.split(','))) for p in parts[:4]]
    if any(len(v)!=368 or v[0]!=0x4137434b or v[12:16]!=identity for v in values):
        raise ValueError('Wrong snapshot source identity')
    if values[0][5]!=1: raise ValueError('Geometry callback not disarmed')
    observations=[]
    for i,v in enumerate(values[1:]):
        if v[16]!=i+1 or v[17]!=3 or v[18] or v[224:256]!=v[272:304]:
            raise ValueError('Failed or unstable metadata snapshot '+str(i))
        obj=v[40:172]
        pair=lambda at:[obj[at//4]&65535,obj[at//4]>>16]
        observations.append(dict(shot=i+1,requested_size=('L','M','S')[i],
            handle=v[21],active_pair=pair(0x90),canvas_pair=pair(0x94),
            origin_pair=pair(0x98),extent_count=obj[0xbc//4]&255,
            object_physical=hex(obj[0xc0//4]),object_capacity=obj[0xc4//4],
            extent_words=v[256:268],encoder_object=obj,stage=v[176:216],values=v))
    return dict(observations=observations,pixel_write=False,firmware_written=False,
                disarmed=True,requested_size_labels_require_user_shot_order=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--live',action='store_true')
    a=p.parse_args();proof=json.loads((a.bundle/'proof.json').read_text())
    if proof['route']!='geometry' or sha((a.bundle/'a7capgeom.ko').read_bytes())!=proof['module_sha256']:
        raise ValueError('Wrong geometry bundle')
    out=ROOT/'.lab/capture-geometry-read'/str(time.time_ns());out.mkdir(parents=True)
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
            raw=f.run((out/'read.so').read_bytes(),'a7gm.bin');(out/'raw.bin').write_bytes(raw)
            result=decode(raw,proof['source_id'])
            result.update(bundle=str(a.bundle.resolve()),module_sha256=proof['module_sha256'])
            (out/'geometry.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps([{k:v for k,v in o.items() if k not in ('values','encoder_object','stage')}
                              for o in result['observations']],indent=2))
        old,sw=service.perform,handoff.SWITCH
        service.perform=collect;handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:service.perform, handoff.SWITCH=old,sw
    print('EVIDENCE',out)

if __name__=='__main__':main()
