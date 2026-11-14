#!/usr/bin/env python3
"""Run original 4.04 generic setting-node machine code, without a camera.

This validates data-model ABI only: no original LCD renderer, ISP, USB or flash.
Sony bytes stay in ignored .lab output, extracted from the user's local firmware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
from elf32 import ELF

ROOT = Path(__file__).resolve().parents[1]
SHA = '0b9f2b855c032fc36cc83386a1fe706a8b59042e52702035a7d1a293b4e9f8a0'
PIECES = [(0x682868, 0x683402-0x682868, 'nodes'), (0x6835a8, 0xf2, 'properties')]
# ARM PLT entries and Thumb interworking tails used by the original component.
STUBS = {
    0x672d20: (0x68361b, True), 0x670b3c: (0x68363b, True),
    0x671c14: (0x68365b, True), 0x674144: (0x68367b, True),
    0x67a510: (0x6835b3, False), 0x672134: (0x6835eb, False),
    0x6738b8: ('release', False), 0x674268: (0x6832a9, False),
    0x674cac: ('release', False), 0x671290: ('allocate', False),
    0x675408: ('allocate', False), 0x679cfc: (0x683309, False),
    0x679120: ('unexpected', False), 0x6754f8: (0x6833b1, False),
}
WIDGET_STUBS={0x572c1c:'widget_set_pages',0x572c26:'widget_set_rows',
               0x572c3a:'widget_set_page',0x572c44:'widget_set_row',
               0x572dca:'widget_has_subcursor',0x573d04:'widget_render',
               0x573d84:'unexpected'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--usr',required=True,type=Path)
    ap.add_argument('--film-curve-menu',action='store_true')
    args=ap.parse_args()
    elf=ELF(args.usr/'lib/CautionConfig.so')
    view=ELF(args.usr/'lib/viewUnified2.so')
    if hashlib.sha256(elf.data).hexdigest()!=SHA: ap.error('Unexpected CautionConfig SHA-256')
    out=ROOT/('.lab/native-adjust-film' if args.film_curve_menu else '.lab/native-adjust');out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)
    asm='.syntax unified\n';sections=[];pieces=[]
    for va,size,name in PIECES:
        data=elf.read(va,size);pieces.append({'va':hex(va),'size':size,'sha256':hashlib.sha256(data).hexdigest()})
        (out/f'{name}.bin').write_bytes(data)
        asm+=f'.section .native_{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((va,f'.native_{name}'))
    # Execute the real layer-one page/row traversal, while recording renderer
    # setter arguments. The old flat graph is a regression counterexample.
    data=view.read(0x5740d4,0x574202-0x5740d4)
    (out/'widget.bin').write_bytes(data)
    asm+='.section .native_widget,"ax"\n.incbin "widget.bin"\n'
    sections.append((0x5740d4,'.native_widget'))
    pieces.append({'library':'viewUnified2.so','va':'0x5740d4','size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    vtable=bytearray(elf.read(0x918ec0,268))
    for offset in range(4,268,4):
        _,sym=elf.relocations[0x918ec0+offset]
        struct.pack_into('<I',vtable,offset,sym['value'])
    (out/'vtable.bin').write_bytes(vtable)
    asm+='.section .native_vtable,"a"\n.incbin "vtable.bin"\n'
    sections.append((0x918ec0,'.native_vtable'))
    asm+='.section .native_got,"a"\n.word 0x918ec0\n'
    sections.append((0x9880b0,'.native_got'))
    for va,(destination,thumb) in STUBS.items():
        name=f'.stub_{va:x}';sections.append((va,name));asm+=f'.section {name},"ax"\n'
        if thumb:
            asm+=f'.thumb\nldr.w ip, [pc, #4]\nbx ip\nnop\n.word {destination}\n'
        else:
            asm+=f'.arm\nldr ip, [pc, #0]\nbx ip\n.word {destination}\n'
    for va,destination in WIDGET_STUBS.items():
        name=f'.widget_stub_{va:x}';sections.append((va,name))
        # 10-byte Thumb veneer fits adjacent setters at either halfword alignment.
        asm+=f'.section {name},"ax"\n.thumb\nmovw ip, #:lower16:{destination}\nmovt ip, #:upper16:{destination}\nbx ip\n'
    (out/'native.S').write_text(asm)
    ld='ENTRY(_start)\nSECTIONS {\n. = 0x100000;\n.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n. = ALIGN(4096);\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    ld+=''.join(f'{name} {va:#x} : {{ *({name}) }}\n' for va,name in sorted(sections))+'}\n'
    (out/'guest.ld').write_text(ld)
    gcc,qemu=shutil.which('arm-none-eabi-gcc'),shutil.which('qemu-system-arm')
    if not gcc or not qemu: ap.error('ARM GCC and QEMU are required')
    subprocess.run([gcc,'-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-nostdlib','-T','guest.ld',
                    *(['-DA7_FL_FILM_CONTROLS'] if args.film_curve_menu else []),
                    str(ROOT/'ui/start.S'),str(ROOT/'research/native_adjust.c'),str(ROOT/'research/native_adjust_harness.c'),'native.S','-lgcc','-o','adjust.elf'],cwd=out,check=True)
    run=subprocess.run([qemu,'-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/adjust.elf,cpu-num=0'],capture_output=True,text=True,timeout=20,check=True)
    (out/'adjust.log').write_text(run.stdout+run.stderr);print(run.stdout,end='')
    if 'NATIVE_ADJUST_TESTS_PASSED' not in run.stdout or 'FAIL' in run.stdout: raise ValueError('Native node fixture failed')
    sources={name:hashlib.sha256((ROOT/'research'/name).read_bytes()).hexdigest() for name in ['native_adjust.h','native_adjust.c','native_adjust_harness.c','native_adjust_fixture.py']}
    report={'caution_sha256':SHA,'view_sha256':hashlib.sha256(view.data).hexdigest(),'extracted_components':pieces,'source_sha256':sources,'scope':'Original node construction, properties, selection, grayout, clone/destruction and actual PAS_SelectListTab page/row traversal. Two-page 6/4 structure plus old-flat negative control; signed backend/nonnegative UI enum mapping. Rendering/backend mocked; no ISP, USB or camera execution.','flash_ready':False,'log':run.stdout.splitlines()}
    if args.film_curve_menu:
        report['scope']='Original page/row traversal and native node selection for the 6/6/3 curve menu, with isolated scalar IDs and Save; fixture labels/backend only'
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': main()
