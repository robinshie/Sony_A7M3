#!/usr/bin/env python3
"""Build the bounded read-only probe, or decode a retrieved camera report."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-menu'
def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--report',type=Path)
    cli.add_argument('--test',action='store_true')
    cli.add_argument('--maps',type=Path,default=ROOT/'.lab/settings-snapshots/settings-1794312669264125000.maps')
    args=cli.parse_args()
    if args.report:
        raw=args.report.read_bytes()
        if len(raw) not in (43968,55620):raise ValueError('Wrong report size')
        w=struct.unpack('<'+str(len(raw)//4)+'I',raw)
        if w[:3]!=(0x41374e4d,1 if len(raw)==43968 else 2,len(raw)) or w[46]>64:raise ValueError('Wrong report header')
        out={'status':w[3],'view_base':hex(w[4]),'caution_base':hex(w[5]),
             'manager':[hex(x) for x in w[6:8]],'manager_vtable':[hex(x) for x in w[8:36]],
             'cs_root':[hex(x) for x in w[36:46]],'count':w[46],'overflow':w[47],'parents':[]}
        for i in range(w[46]):
            at=48+i*171;node=w[at+1:at+11];n=node[2]
            if n>32:raise ValueError('Invalid child count')
            children=[]
            for j in range(n):
                c=w[at+11+j*5:at+16+j*5]
                children.append(dict(zip(('pointer','vtable','title','process','exec'),map(hex,c))))
            out['parents'].append({'address':hex(w[at]),'relative':hex(w[at]-w[4]),
                                   'node':[hex(x) for x in node],'children':children})
        if w[1]==2:
            out['ancestors']=[]
            if w[10992]>8:raise ValueError('Wrong ancestor count')
            for i in range(w[10992]):
                at=10993+i*364;node=w[at+2:at+12];n=node[2]
                if n>32:raise ValueError('Wrong page count')
                pages=[]
                for j in range(n):
                    p=w[at+12+j*11:at+23+j*11]
                    pages.append({'address':hex(p[0]),'relative':hex(p[0]-w[4]),'node':[hex(x) for x in p[1:]]})
                out['ancestors'].append({'source':hex(w[at]),'address':hex(w[at+1]),
                                         'relative':hex(w[at+1]-w[4]),'node':[hex(x) for x in node],'pages':pages})
        print(json.dumps(out,indent=2));return
    OUT.mkdir(parents=True,exist_ok=True)
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC',
                    '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables',
                    '-fno-asynchronous-unwind-tables','-c',str(ROOT/'research/native_menu_probe.c'),
                    '-o',str(OUT/'probe.o')],check=True)
    subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',
                    str(OUT/'probe.o'),'-o',str(OUT/'probe.so')],check=True)
    data=(OUT/'probe.so').read_bytes()
    if len(data)>16384:raise ValueError('Probe exceeds service payload limit')
    if args.test:
        raw=args.maps.read_bytes()
        if len(raw)>=65536:raise ValueError('Maps fixture too large')
        (OUT/'actual-maps.h').write_text('static const unsigned char actual_maps[]={'+','.join(map(str,raw+b'\0'))+'};\n')
        # Independent bare-metal startup: constructor is never automatically run.
        (OUT/'probe-start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
 cpsid if
 ldr sp,=0x41000000
 ldr r0,=__bss_start
 ldr r1,=__bss_end
 mov r2,#0
1: cmp r0,r1
 strlo r2,[r0],#4
 blo 1b
 bl guest_main
2: wfi
 b 2b
.section .note.GNU-stack,"",%progbits
''')
        (OUT/'probe-guest.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x40200000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }\n')
        subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os',
                        '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
                        '-nostdlib','-I',str(OUT),'-T','probe-guest.ld','probe-start.S',
                        str(ROOT/'research/native_menu_probe_harness.c'),'-lgcc','-o','probe-test.elf'],cwd=OUT,check=True)
        r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults',
                          '-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio',
                          '-semihosting-config','enable=on,target=native','-device',
                          f'loader,file={OUT}/probe-test.elf,cpu-num=0'],capture_output=True,timeout=10,check=True)
        log=r.stdout+r.stderr;(OUT/'probe-qemu.log').write_bytes(log);print(log.decode(),end='')
        if b'NATIVE_MENU_PROBE_PASSED' not in r.stdout or b'FAIL ' in log:raise ValueError('Probe fixture failed')
        sources=['research/native_menu_probe'+s for s in ('.c','.py','_harness.c')]+['payloads/a7-runtime-probe.c']
        proof={'probe_sha256':hashlib.sha256(data).hexdigest(),'probe_bytes':len(data),'report_bytes':55620,
               'maps_sha256':hashlib.sha256(raw).hexdigest(),'qemu_log_sha256':hashlib.sha256(log).hexdigest(),
               'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
               'scope':'Original camera maps plus modeled mapped nodes; memory bounds/alignment/device exclusion/deadline; no USB or live camera execution'}
        (OUT/'probe-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'path':str(OUT/'probe.so'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                      'report':'/tmp/jiritsu/a7flnodes.bin','report_bytes':55620,'report_version':2},indent=2))
if __name__=='__main__':main()
