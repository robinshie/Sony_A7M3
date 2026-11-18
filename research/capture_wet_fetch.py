#!/usr/bin/env python3
"""Read frozen vignette samples; compare against a scalar fixed-point oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
POINTS = ((0, 0), (5992, 0), (0, 3992), (5992, 3992), (2996, 1996))
SOURCE = r'''
static struct {int status;unsigned size[6];char data[6][4096];} result;
static long sc(long n,long a,long b,long c){
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
__attribute__((constructor))static void run(void){
 const char *paths[]={"/sys/module/a7capwet/parameters/auto_sample0",
  "/sys/module/a7capwet/parameters/auto_sample1","/sys/module/a7capwet/parameters/auto_sample2",
  "/sys/module/a7capwet/parameters/auto_film0","/sys/module/a7capwet/parameters/auto_film1","/sys/module/a7capwet/parameters/auto_film2"};
 result.status=-1;
 for(unsigned i=0;i<6;i++){
  long fd=sc(5,(long)paths[i],0,0);if(fd<0)goto output;
  long n=0;unsigned pos=0;
  while(pos<4096){n=sc(3,fd,(long)(result.data[i]+pos),4096-pos);if(n<=0)break;pos+=n;}
  long closed=sc(6,fd,0,0);
  if(n<0||closed||!pos||pos>=4096)goto output;
  result.size[i]=pos;
 }
 result.status=0;
output:;
 long fd=sc(5,(long)"/tmp/jiritsu/a7af.bin",1|64|128,0600);if(fd<0)return;
 unsigned pos=0;while(pos<sizeof result){long n=sc(4,fd,(long)((char*)&result+pos),sizeof result-pos);if(n<=0)break;pos+=n;}
 long closed=sc(6,fd,0,0);if(pos!=sizeof result||closed)sc(10,(long)"/tmp/jiritsu/a7af.bin",0,0);
}
'''


def trunc(n, divisor):
    return n // divisor if n >= 0 else -((-n) // divisor)


def gain(x, y, strength, width, height):
    qx = (2*x-(width-1))**2 * 1024 // ((width-1)**2)
    qy = (2*y-(height-1))**2 * 1024 // ((height-1)**2)
    q = (qx+qy)//2
    t = 0 if q <= 128 else (q-128)*1024//896
    weight = (t*t//1024)*(3072-2*t)//1024
    amplitude = trunc(strength*(768 if strength < 0 else 1024), 9)
    return 1024+trunc(amplitude*weight, 1024)


def points(width,height):
    return ((0,0),(width-8,0),(0,height-8),(width-8,height-8),(((width-8)//2)&~1,(height-8)//2))

def oracle(before, strength, width, height):
    out = bytearray(before)
    for point, (x0, y0) in enumerate(points(width,height)):
        for y in range(8):
            for x in range(0, 8, 2):
                at = point*128+y*16+x*2
                g0, g1 = gain(x0+x, y0+y, strength,width,height), gain(x0+x+1, y0+y, strength,width,height)
                for i, factor in enumerate(((g0+g1)//2, g0, (g0+g1)//2, g1)):
                    origin = 0 if i % 2 else 128
                    out[at+i] = min(255, max(0, origin+trunc((before[at+i]-origin)*factor, 1024)))
    return bytes(out)


def nearest(n,d):
    return (n+d//2)//d if n>=0 else -((-n+d//2)//d)

def wet_oracle(before):
    out=bytearray(before)
    knots=(0,10,25,50,75,91,100);tones=(0,18,105,500,890,985,1000)
    for at in range(0,len(out),4):
        cb,cr=before[at]-128,before[at+2]-128
        rgb_shift=(nearest(cr*40154,25500),nearest(-cb*4777-cr*11938,25500),nearest(cb*47318,25500))
        out[at]=out[at+2]=128
        for offset in (1,3):
            y=before[at+offset]
            lum=sum(weight*max(0,min(255,y+shift)) for weight,shift in zip((10,32,58),rgb_shift))
            k=next((j for j in range(6) if lum<=255*knots[j+1]),5)
            step=knots[k+1]-knots[k]
            out[at+offset]=nearest(255*step*tones[k]+(lum-255*knots[k])*(tones[k+1]-tones[k]),1000*step)
    return bytes(out)

def decode(raw,completed=3):
    if len(raw)!=24604:raise ValueError('Incomplete wet sample result')
    status,*lengths=struct.unpack_from('<i6I',raw)
    if status or any(not 0<n<4096 for n in lengths):raise ValueError('Sample read failed')
    records=[list(map(int,raw[28+i*4096:28+i*4096+n].decode().strip().split(','))) for i,n in enumerate(lengths)]
    result=[]
    for i in range(completed):
        w=records[i];mid=records[i+3]
        if len(w)!=334 or w[:5]!=[0x41375647,i,0,0,0] or len(mid)!=160:raise ValueError('Wrong wet diagnostic identity')
        width,height,stride,offset,ow,oh,seed,ticks=w[326:334]
        if w[5] not in (0x1a000000,0x24000000) or [width,height,stride,offset,ow,oh] not in (
            [6000,4000,12160,160,6000,4000],[3936,4000,12000,160,3936,2624],[3008,4000,12000,160,3008,2000]):
            raise ValueError('Unverified source geometry')
        before=struct.pack('<160I',*w[6:166]);film=struct.pack('<160I',*mid);after=struct.pack('<160I',*w[166:326])
        verified=film==before and after==wet_oracle(before) and all(v==128 for v in after[::2])
        result.append(dict(index=i,source_size=[width,height],output_size=[ow,oh],stride=stride,offset=offset,
            ticks=ticks,physical=hex(w[5]),points=points(width,height),verified=verified,
            source_chroma_changed=before[::2]!=after[::2],before_hex=before.hex(),film_hex=film.hex(),after_hex=after.hex()))
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--build-only', action='store_true')
    p.add_argument('--partial', action='store_true')
    a = p.parse_args()
    b = a.bundle.resolve()
    proof = json.loads((b/'proof.json').read_text())
    if proof['route'] != 'wet' or proof['module_name'] != 'a7capwet' or not proof['diagnostic']:
        raise ValueError('Expected vignette diagnostic bundle')
    for n, h in proof['source_sha256'].items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != h:
            raise ValueError('Candidate source changed: '+n)
    (b/'fetch-wet.c').write_text(SOURCE)
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft',
                    '-fPIC', '-Os', '-ffreestanding', '-fno-builtin', '-nostdlib', '-shared',
                    '-Wl,--no-undefined', '-Wl,-z,noexecstack', '-Wall', '-Wextra', '-Werror',
                    'fetch-wet.c', '-o', 'fetch-wet.so'], cwd=b, check=True)
    if a.build_only:
        return
    runs = [r for r in proof['live'] if r['action'] == 'collect' and r['verified']]
    if not runs:
        raise ValueError('Collect and disarm before reading samples')
    v = runs[-1]['values']
    if v[353]!=86672 or v[5] != 1 or not 1 <= v[355] <= 3 or (not a.partial and (v[355] != 3 or v[357] or v[18] or v[345] or v[310] != 1)):
        raise ValueError('Require exactly three successful captures')
    from camera import handoff, service
    def collect(camera, action):
        f = service.Factory(camera)
        if action != 'settings-snapshot' or f.contents('/version.txt') != b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005)) != b'ILCE-7M3'+bytes(8):
            raise ValueError('Wrong camera/build')
        raw = f.run((b/'fetch-wet.so').read_bytes(), 'a7af.bin')
        (b/'wet-samples.bin').write_bytes(raw)
        frames = decode(raw, v[355])
        result = dict(frames=frames, passed=not a.partial and v[355]==3 and not v[357] and all(r['verified'] for r in frames),
                      completed=v[355],failed=v[357],partial=a.partial,
                      source_samples_verified=all(r['verified'] for r in frames), jpeg_effect_verified=False, firmware_written=False,
                      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      sample_sha256=hashlib.sha256(raw).hexdigest(), kernel_sha256=proof['module_sha256'])
        (b/'wet-samples.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(passed=result['passed'],frames=[{k:v for k,v in r.items() if not k.endswith('_hex')} for r in frames]), indent=2))
        if not result['source_samples_verified']:
            raise ValueError('Captured pixels differ from reference')
    old, sw = service.perform, handoff.SWITCH
    service.perform = collect
    handoff.SWITCH += ' --host-identity-check'
    try:
        handoff.run('settings-snapshot')
    finally:
        service.perform, handoff.SWITCH = old, sw


if __name__ == '__main__':
    main()
