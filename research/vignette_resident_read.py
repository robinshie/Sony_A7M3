#!/usr/bin/env python3
"""Read-only r16 inspection: resident module, schema-5 settings and capture kernel."""
import argparse
import ctypes as C
import hashlib
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera import native_status


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binding', type=Path, required=True)
    p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--live', action='store_true')
    a = p.parse_args()
    kp = json.loads((a.kernel/'proof.json').read_text())
    mp = json.loads((a.binding/'module-proof.json').read_text())
    if (kp['route'] != 'vignette' or kp['module_name'] != 'a7capvig'
            or kp['module_sha256'] != mp['kernel_sha256']
            or sha(a.kernel/'a7capvig.ko') != kp['module_sha256']):
        raise ValueError('Vignette kernel identity differs')
    profile = native_status.Profile(
        ROOT/'.lab/native-install-bound', a.binding.resolve()/'module-proof.json',
        a.probe.resolve(), ROOT/'.lab/native-fl-01',
        replacement_binding=a.binding.resolve(),
        capture_proof=ROOT/'.lab/lut3d-fl2-reference-private/proof.json')
    out = ROOT/'.lab/vignette-resident-read'/str(time.time_ns())
    out.mkdir(parents=True)
    source = r'''
static struct { int lengths[4]; char report[4096], selection[32], diagnostic[32], uptime[64]; } r;
static long sc(long n,long a,long b,long c) {
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc"); return r0;
}
static int readfile(const char*p,char*b,unsigned cap) {
 long fd=sc(5,(long)p,0,0); if(fd<0)return fd; unsigned pos=0;
 while(pos<cap) { long n=sc(3,fd,(long)(b+pos),cap-pos);
  if(n<0){sc(6,fd,0,0);return n;} if(!n)break; pos+=n;
 } long c=sc(6,fd,0,0); return c?c:(int)pos;
}
__attribute__((constructor))static void run(void) {
 r.lengths[0]=readfile("/sys/module/a7capvig/parameters/report",r.report,sizeof r.report);
 r.lengths[1]=readfile("/sys/module/a7capvig/parameters/selection",r.selection,sizeof r.selection);
 r.lengths[2]=readfile("/sys/module/a7capvig/parameters/diagnostic",r.diagnostic,sizeof r.diagnostic);
 r.lengths[3]=readfile("/proc/uptime",r.uptime,sizeof r.uptime);
 long fd=sc(5,(long)"/tmp/jiritsu/a7vg.bin",1|64|128,0600); if(fd<0)return;
 long n=sc(4,fd,(long)&r,sizeof r),c=sc(6,fd,0,0);
 if(n!=sizeof r||c)sc(10,(long)"/tmp/jiritsu/a7vg.bin",0,0);
}
'''
    (out/'kernel-read.c').write_text(source)
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm',
        '-mfloat-abi=soft', '-fPIC', '-Os', '-ffreestanding', '-fno-builtin',
        '-nostdlib', '-shared', '-Wl,--no-undefined', '-Wl,-z,noexecstack',
        '-Wall', '-Wextra', '-Werror', str(out/'kernel-read.c'),
        '-o', str(out/'kernel-read.so')], check=True)
    (out/'decode.c').write_text('''#include "a7-fl-runtime-prefs.h"
int summarize(const uint8_t *a,const uint8_t*b,const uint8_t*h,const char*build,int*out) {
 struct a7_fl_preference p; int r=a7_fl_preference_choose(&p,a,128,b,128,h,build);
 if(r<0)return r; out[0]=r;out[1]=p.schema;out[2]=p.generation;out[3]=p.enabled;
 for(unsigned bank=0;bank<3;bank++)for(unsigned f=0;f<7;f++)out[4+bank*7+f]=p.film[bank][f];
 for(unsigned f=0;f<8;f++)out[25+f]=p.parameters[f];
 for(unsigned bank=0;bank<3;bank++)out[33+bank]=p.vignette[bank]; return 0;
}
''')
    subprocess.run(['clang', '-dynamiclib', '-O2', '-DA7_FL_FILM_CONTROLS',
        '-DA7_FL_CAPTURE_HALATION', '-DA7_FL_CAPTURE_VIGNETTE', '-DA7_FL_DUAL_LOOK',
        '-DA7_FL_LEICA_LOOK', '-DA7_FL_LOOK_BANKS', '-I'+str(ROOT/'payloads'),
        str(out/'decode.c'), str(ROOT/'payloads/a7-fl-runtime-prefs.c'),
        str(ROOT/'payloads/a7-fl-runtime.c'), '-o', str(out/'decode.dylib')], check=True)
    decode = C.CDLL(str(out/'decode.dylib')).summarize
    decode.argtypes = [C.c_char_p]*4+[C.POINTER(C.c_int)]
    decode.restype = C.c_int

    def decode_slots(slots):
        result = (C.c_int*36)()
        digest = hashlib.sha256((ROOT/'.lab/native-fl-01/00030004.bin').read_bytes()).digest()
        build = b'37114_13.2026020901'.ljust(24, b'\0')
        if any(len(s) != 128 for s in slots) or decode(*slots, digest, build, result):
            raise ValueError('No verified saved preference')
        v = list(result)
        return dict(slot=v[0], schema=v[1], generation=v[2], mode=v[3],
                    film=[v[4+i*7:11+i*7] for i in range(3)],
                    parameters=v[25:33], vignette=v[33:36])

    baseline = ROOT/'.lab/native-fl-releases/update-r15-halation-haw04xx1/write-1794721551114287000'
    old = decode_slots([(baseline/f'preference-before-{i}.bin').read_bytes() for i in range(2)])
    if old['schema'] != 4 or old['vignette'] != [0, 0, 0]:
        raise ValueError('Legacy slot decoder regression')
    if not a.live:
        print('VIGNETTE_RESIDENT_READER_PREPARED', out)
        return
    from camera import handoff, service

    def collect(camera, action):
        if action != 'settings-snapshot':
            raise ValueError('Unexpected action')
        result = native_status.inspect_camera(camera, profile, out, True)
        f = service.Factory(camera)
        raw = f.run((out/'kernel-read.so').read_bytes(), 'a7vg.bin')
        (out/'kernel-read.bin').write_bytes(raw)
        if len(raw) != 4240:
            raise ValueError('Wrong kernel report length')
        lengths = struct.unpack_from('<4i', raw)
        kernel = dict(read_status=list(lengths))
        if all(0 < n < cap for n, cap in zip(lengths, (4096, 32, 32, 64))):
            parts = [raw[pos:pos+n].decode().strip()
                     for pos, n in zip((16, 4112, 4144, 4176), lengths)]
            vals = list(map(int, parts[0].split(',')))
            if len(vals) != 368 or vals[0] != 0x4137434b or vals[12:16] != kp['source_id']:
                raise ValueError('Wrong booted kernel identity')
            signed = lambda n: (n+2**31) % 2**32-2**31
            kernel.update(armed=bool(vals[1] and vals[11] and not vals[5]),
                selection=int(parts[1]), diagnostic=int(parts[2]),
                completed=vals[355], failed=vals[357], last_grain=vals[361],
                last_halation=signed(vals[358]), last_vignette=signed(vals[362]),
                lock_attempts=vals[363], kernel_sha256=kp['module_sha256'], uptime=parts[3])
        slots = [f.contents('/setting/A7FL%d.CFG' % i, maximum=160) for i in range(2)]
        for i, slot in enumerate(slots):
            (out/f'preference-{i}.bin').write_bytes(slot)
        saved = decode_slots(slots)
        mode = saved['mode']
        desired = ((mode << 14) | ((saved['vignette'][mode-1]+9) << 9)
                   | ((saved['film'][mode-1][1]+9) << 4) | saved['film'][mode-1][0]) if mode else 0
        runtime = result.get('runtime') or {}
        result.update(vignette_kernel=kernel, saved=saved,
            kernel_matches_saved=bool(kernel.get('armed') and kernel.get('diagnostic') == 0
                                      and kernel.get('selection') == desired),
            runtime_matches_saved=all(runtime.get(k) == saved[v] for k, v in
                (('generation', 'generation'), ('mode', 'mode'), ('parameters', 'parameters'))),
            persistent_device_writes=False)
        (out/'vignette-status.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
        print('EVIDENCE', out)

    old_perform, old_switch = service.perform, handoff.SWITCH
    service.perform = collect
    handoff.SWITCH += ' --host-identity-check'
    try:
        handoff.run('settings-snapshot')
    finally:
        service.perform, handoff.SWITCH = old_perform, old_switch


if __name__ == '__main__':
    main()
