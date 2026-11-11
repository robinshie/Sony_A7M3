#!/usr/bin/env python3
"""Validate native insertion adapter against original ARM process dispatch.

Original instruction blocks and dispatch table are extracted from the user's
local 4.04 image, never committed. QEMU executes them with a modeled process
element factory. This is not a complete camera/display emulator or flash image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from elf32 import ELF
from creative_dispatch import VIEW_SHA

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-menu'
def sha(data): return hashlib.sha256(data).hexdigest()
def run(args,**kw): return subprocess.run(args,check=True,**kw)

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--usr',type=Path,required=True)
    args=cli.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    e=ELF(args.usr/'lib/viewUnified2.so')
    if sha(e.data)!=VIEW_SHA: raise ValueError('Pinned original A7M3 4.04 view2 required')
    ranges={'lookup':(0x2f2764,0x34),'stock_get':(0x2f2a2a,0x18),
            'stock_set':(0x2f2844,0x18),'stock_invalid':(0x2f28a0,0x14),
            'dispatch_table':(0x72decc,618*4)}
    asm='.syntax unified\n'
    for name,(a,n) in ranges.items():
        (OUT/(name+'.bin')).write_bytes(e.read(a,n))
        asm+=f'.section .{name},"a'+('x' if name!='dispatch_table' else '')+'"\n'
        if name!='dispatch_table':asm+='.thumb\n'
        asm+=f'.global {name}\n'
        if name!='dispatch_table':asm+='.thumb_func\n'
        asm+=f'{name}: .incbin "{name}.bin"\n'
    asm+='''.section .factory,"ax"
.thumb
b.w mock_element_factory
.section .note.GNU-stack,"",%progbits
'''
    (OUT/'native.S').write_text(asm)
    (OUT/'start.S').write_text('''.syntax unified
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
    ld='ENTRY(_start)\nSECTIONS {\n. = 0x40200000;\n.text : { *(.text.start) *(.text*) }\n'
    ld+='.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    placements={**{name:0x40000000+a for name,(a,_) in ranges.items()},'factory':0x40403840}
    ld+=''.join(f'.{name} {a:#x} : {{ *(.{name}) }}\n' for name,a in sorted(placements.items(),key=lambda x:x[1]))+'}\n'
    (OUT/'guest.ld').write_text(ld)
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror',
           '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
           '-I',str(ROOT/'research')]
    run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','guest.ld','start.S','native.S',
         str(ROOT/'research/native_menu.c'),str(ROOT/'research/native_menu_harness.c'),'-lgcc','-o','menu-test.elf'],cwd=OUT)
    run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/'research/native_menu.c'),'-o','menu.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack','menu.o','-o','liba7-native-menu.so'],cwd=OUT)
    r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-smp','1','-m','1024',
           '-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none',
           '-serial','stdio','-semihosting-config','enable=on,target=native','-device',
           f'loader,file={OUT}/menu-test.elf,cpu-num=0'],capture_output=True,timeout=30)
    log=r.stdout+r.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if b'NATIVE_MENU_PASSED' not in r.stdout or b'FAIL ' in log: raise ValueError('Native menu test failed')
    sources=['research/native_menu'+s for s in ('.h','.c','.py','_harness.c')]
    proof={'original_view_sha256':VIEW_SHA,'original_instruction_ranges':ranges,
           'source_sha256':{s:sha((ROOT/s).read_bytes()) for s in sources},
           'files_sha256':{s:sha((OUT/s).read_bytes()) for s in ('menu-test.elf','liba7-native-menu.so','qemu.log')},
           'scope':'Original manager lookup/scalar get/set/invalid instructions, real 618-entry dispatch table; process element factory modeled; guarded parent insertion uses mapped object fixture',
           'stock_ids_tested':618,'custom_ids_tested':9,'camera_integration':False,
           'native_display_rendered':False,'flash_ready':False}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':main()
