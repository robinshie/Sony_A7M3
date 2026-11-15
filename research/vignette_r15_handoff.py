#!/usr/bin/env python3
"""Temporarily disarm the accepted r15 film hook for the vignette test.

No persistent camera files/settings are changed. A cold boot restores r15.
The live baseline, module source identity and packed film selection must all match.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASELINE = 'a44876fb9136b4fe31c9d82ad143bf87d9b10c3d05fc8b0ba77f0348a6c3324d'
IDENTITY = [3507440315, 21543379, 1734279086, 502465496]
SOURCE = r'''
static struct { int status,before_n,after_n,selection_n,selected;
    char before[4096],after[4096],selection[32]; } r;
static unsigned values[368];
static long sc(long n,long a,long b,long c){
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static int readfile(const char*p,char*b,unsigned cap){
 long fd=sc(5,(long)p,0,0);if(fd<0)return fd;
 unsigned pos=0;long n=0;
 while(pos<cap){n=sc(3,fd,(long)(b+pos),cap-pos);if(n<=0)break;pos+=n;}
 long c=sc(6,fd,0,0);return n<0?n:c?c:(int)pos;
}
static int number(const char **p,const char *end,unsigned *v){
 unsigned n=0,count=0;
 while(*p<end&&**p>='0'&&**p<='9'){
  unsigned digit=(unsigned)(*(*p)++-'0');
  if(n>429496729U||(n==429496729U&&digit>5))return 0;
  n=n*10+digit;count++;
 }
 *v=n;return count!=0;
}
static int decode(const char *p,int n){
 if(n<=0||n>=4096)return 0;
 const char *end=p+n;
 for(unsigned i=0;i<368;i++){
  if(!number(&p,end,values+i))return 0;
  if(i<367&&(p==end||*p++!=','))return 0;
 }
 if(p<end&&*p=='\n')p++;
 return p==end&&values[0]==0x4137434b&&values[3]==1&&values[4]==1&&
  values[12]==3507440315U&&values[13]==21543379U&&
  values[14]==1734279086U&&values[15]==502465496U;
}
__attribute__((constructor))static void run(void){
 const char *report="/sys/module/a7capfilm/parameters/report";
 r.status=1;r.before_n=readfile(report,r.before,sizeof r.before);
 if(!decode(r.before,r.before_n))goto output;
 r.status=2;r.selection_n=readfile("/sys/module/a7capfilm/parameters/selection",r.selection,sizeof r.selection);
 if(r.selection_n<=0||r.selection_n>=32)goto output;
 const char *p=r.selection,*end=p+r.selection_n;unsigned selected;
 if(!number(&p,end,&selected))goto output;
 if(p<end&&*p=='\n')p++;
 if(p!=end||(selected!=0&&(selected>=2048||(selected>>9)<1||(selected>>9)>3||(selected&15)>9||((selected>>4)&31)>18)))goto output;
 r.selected=selected;
 r.status=3;
 if(values[1]!=1||values[11]!=1||values[5]>1)goto output;
 if(!values[5]){
  long fd=sc(5,(long)"/sys/module/a7capfilm/parameters/disarm",1,0);
  if(fd<0)goto output;
  long n=sc(4,fd,(long)"1",1),c=sc(6,fd,0,0);
  if(n!=1||c)goto output;
 }
 r.status=4;r.after_n=readfile(report,r.after,sizeof r.after);
 if(!decode(r.after,r.after_n)||values[5]!=1)goto output;
 r.status=0;
output:;
 long fd=sc(5,(long)"/tmp/jiritsu/a7hh.bin",1|64|128,0600);if(fd<0)return;
 unsigned pos=0;while(pos<sizeof r){long n=sc(4,fd,(long)((char*)&r+pos),sizeof r-pos);if(n<=0)break;pos+=n;}
 long c=sc(6,fd,0,0);if(pos!=sizeof r||c)sc(10,(long)"/tmp/jiritsu/a7hh.bin",0,0);
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    out = ROOT / '.lab/vignette-r15-handoff' / str(time.time_ns())
    out.mkdir(parents=True)
    (out / 'handoff.c').write_text(SOURCE)
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm',
                    '-mfloat-abi=soft', '-fPIC', '-Os', '-ffreestanding',
                    '-fno-builtin', '-nostdlib', '-shared', '-Wl,--no-undefined',
                    '-Wl,-z,noexecstack', '-Wall', '-Wextra', '-Werror',
                    str(out / 'handoff.c'), '-o', str(out / 'handoff.so')], check=True)
    digest = lambda b: hashlib.sha256(b).hexdigest()
    proof = dict(baseline=BASELINE, source_id=IDENTITY,
                 helper_sha256=digest((out / 'handoff.so').read_bytes()),
                 source_sha256=digest(Path(__file__).read_bytes()),
                 firmware_written=False, settings_written=False, live=False)
    def save():
        (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    save()
    if args.live:
        from camera import handoff, service
        def collect(camera, action):
            if action != 'settings-snapshot':
                raise ValueError('Unexpected action')
            f = service.Factory(camera)
            if (f.contents('/version.txt') != b'37114_13.2026020901' or
                    bytes(camera.readBackup(0x3e0005)) != b'ILCE-7M3' + bytes(8)):
                raise ValueError('Wrong camera/build')
            module = f.contents('/usr/lib/a7fl.so')
            if digest(module) != BASELINE:
                raise ValueError('Expected accepted r15; no handoff performed')
            (out / 'r15-readback.so').write_bytes(module)
            before = [f.contents('/setting/A7FL%d.CFG' % i, maximum=160) for i in range(2)]
            if any(len(slot) != 128 for slot in before):
                raise ValueError('Preference backup is incomplete')
            for i, slot in enumerate(before):
                (out / ('preference-%d.bin' % i)).write_bytes(slot)
            raw = f.run((out / 'handoff.so').read_bytes(), 'a7hh.bin')
            (out / 'live.bin').write_bytes(raw)
            if len(raw) != 8244:
                raise ValueError('Unexpected handoff report size')
            status, bn, an, sn, selection = struct.unpack_from('<5i', raw)
            proof.update(live=True, status=status, sizes=[bn, an, sn], selection=selection)
            save()
            if status:
                raise ValueError('Handoff stopped at guard %d; inspect evidence' % status)
            values = list(map(int, raw[4116:4116+an].decode().strip().split(',')))
            if len(values) != 368 or values[12:16] != IDENTITY or values[5] != 1:
                raise ValueError('Disarm readback identity mismatch')
            after = [f.contents('/setting/A7FL%d.CFG' % i, maximum=160) for i in range(2)]
            if before != after:
                raise ValueError('Settings changed during handoff')
            proof.update(disarmed=True, settings_unchanged=True, temporary_files_removed=True)
            save()
            print(json.dumps(proof, indent=2), flush=True)
        old, sw = service.perform, handoff.SWITCH
        service.perform = collect
        handoff.SWITCH += ' --host-identity-check'
        try:
            handoff.run('settings-snapshot')
        finally:
            service.perform, handoff.SWITCH = old, sw
    print('EVIDENCE', out)


if __name__ == '__main__':
    main()
