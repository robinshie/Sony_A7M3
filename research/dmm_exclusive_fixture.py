#!/usr/bin/env python3
"""Execute original DMM Open/Close in QEMU with private resource records.

No driver is loaded on the camera. A DMM exclusion state is not proof of a
shooting-stage fence: all actual image consumers must participate in DMM.
"""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from elf32 import ELF
ROOT=Path(__file__).resolve().parents[1]
PIN='f0df6a0e335e8a1bf71c01b9a7d1caeefdb8c7353f96ec8c699a0b3c8d6e1ae6'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--module',required=True,type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'.lab/dmm-exclusive');a=p.parse_args()
    e=ELF(a.module)
    if sha(e.data)!=PIN:raise ValueError('Requires pinned original 4.04 dmm.ko')
    code=e.section(1)
    if e.sections[1][5]!=0xc3ec:raise ValueError('Unexpected text section')
    ranges={'handle':(0x85a4,0x85fc),'lease':(0x889c,0x8b1c)}
    reloc={0x8a24:0x42000000,0x8b18:0x42000000,
           **{x:0x41000000 for x in range(0x8a8c,0x8aa8,4)}}
    # Assert the entire relocation set of the copied native routines.
    seen={}
    for sec in e.sections:
        if sec[1]!=9 or sec[7]!=1:continue
        for pos in range(sec[4],sec[4]+sec[5],sec[9]):
            at,info=struct.unpack_from('<II',e.data,pos)
            if any(lo<=at<hi for lo,hi in ranges.values()):seen[at]=info&255
    if seen!={at:2 for at in reloc}:raise ValueError('Unexpected native relocations')
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'proof.json').unlink(missing_ok=True)
    asm='.syntax unified\n.arm\n';sections=[]
    for name,(lo,hi) in ranges.items():
        data=bytearray(code[lo:hi])
        for at,base in reloc.items():
            if lo<=at<hi:
                addend=struct.unpack_from('<I',code,at)[0]
                if base==0x42000000 and addend!=0x94678:raise ValueError('Unexpected state base')
                struct.pack_into('<I',data,at-lo,base+addend)
        (a.out/(name+'.bin')).write_bytes(data)
        asm+=f'.section .{name},"ax"\n.incbin "{name}.bin"\n';sections.append((0x41000000+lo,name))
    asm+='.section .note.GNU-stack,"",%progbits\n';(a.out/'native.S').write_text(asm)
    (a.out/'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
 cpsid if
 ldr sp,=0x40800000
 bl guest_main
1: wfi
 b 1b
.section .note.GNU-stack,"",%progbits
''')
    ld='ENTRY(_start)\nSECTIONS { . = 0x40200000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { *(.bss*) *(COMMON) }\n'
    ld+=''.join(f'.{n} {addr:#x} : {{ *(.{n}) }}\n' for addr,n in sections)+'}\n';(a.out/'guest.ld').write_text(ld)
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a15','-marm','-O2','-Wall','-Wextra','-Werror',
        '-ffreestanding','-fno-builtin','-nostdlib','-T','guest.ld','start.S','native.S',
        str(ROOT/'research/dmm_exclusive_harness.c'),'-lgcc','-o','test.elf'],cwd=a.out,check=True)
    r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults',
        '-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio',
        '-semihosting-config','enable=on,target=native','-device',f'loader,file={a.out.resolve()}/test.elf,cpu-num=0'],capture_output=True,timeout=20)
    log=r.stdout+r.stderr;(a.out/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if r.returncode or b'DMM_EXCLUSIVE_PASSED' not in log or b'FAIL' in log:raise ValueError('Native DMM exclusion test failed')
    sources=['research/dmm_exclusive_fixture.py','research/dmm_exclusive_harness.c','research/elf32.py']
    (a.out/'proof.json').write_text(json.dumps(dict(module_sha256=PIN,native_ranges=ranges,
        relocations={hex(k):hex(v) for k,v in reloc.items()},
        source_sha256={n:sha((ROOT/n).read_bytes()) for n in sources},log=log.decode(),
        original_open_close_executed=True,private_resource_records=True,
        actual_frame_ownership_verified=False,cache_sync_verified=False,
        camera_written=False,flash_ready=False),indent=2)+'\n')
if __name__=='__main__':main()
