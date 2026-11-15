#!/usr/bin/env python3
"""Exercise four call-site bridges and CPU exceptions; no native encoder runs."""
import argparse,json,struct,subprocess
from pathlib import Path
from kernel_probe import ROOT,sha,PINS
SITES=[(0x33588c,0x354894),(0x11adf0,0x1180b8),(0x4e70e0,0x7c248c),(0x45ce58,0x7bde2e)]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--avcam',type=Path,required=True)
    p.add_argument('--detail',action='store_true');p.add_argument('--vfx',action='store_true');p.add_argument('--frame',action='store_true');p.add_argument('--early',action='store_true');p.add_argument('--lease',action='store_true');p.add_argument('--grain',action='store_true');p.add_argument('--full',action='store_true');p.add_argument('--fast',action='store_true');p.add_argument('--repeat',action='store_true');p.add_argument('--banks',action='store_true');a=p.parse_args()
    if a.banks:a.repeat=True
    if a.repeat:a.full=True
    if a.fast:a.full=True
    if a.full:a.grain=True
    if a.grain:a.lease=True
    if a.lease:a.early=True
    if a.early:a.frame=True
    if a.frame:a.vfx=True
    if a.detail and a.vfx:p.error('Choose only one route')
    sites=[(0x134ccc,0x134bb0),(0x134c3c,0x484bb8),(0x11b344,0x11ac9c),(0x11b098,0x11a680)] if a.vfx else SITES
    if a.early:sites[2]=(0x11c4e8,0x6b6032)
    data=a.avcam.read_bytes()
    if sha(data)!=PINS['avcam']:raise ValueError('Wrong AV-CAM')
    from yc_route_audit import call
    from capture_grain_route import Flat
    pins=[call(Flat(data),s,t,'bl') for s,t in sites]
    out=ROOT/('.lab/capture-banks-test' if a.banks else '.lab/capture-repeat-test' if a.repeat else '.lab/capture-fast-test' if a.fast else '.lab/capture-full-test' if a.full else '.lab/capture-grain-test' if a.grain else '.lab/capture-lease-test' if a.lease else '.lab/capture-early-test' if a.early else '.lab/capture-frame-test' if a.frame else '.lab/capture-vfx-test' if a.vfx else '.lab/capture-detail-test' if a.detail else '.lab/capture-multi-test');out.mkdir(exist_ok=True)
    (out/'proof.json').unlink(missing_ok=True)
    asm='''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
 cpsid if
 cps #0x1b
 ldr sp,=0x40ff0000
 cps #0x13
 ldr r0,=vectors
 mcr p15,0,r0,c12,c0,0
 isb
 ldr sp,=0x41000000
 bl guest_main
1: b 1b
.balign 32
vectors:
 b .
 b undef_entry
 b .
 b .
 b .
 b .
 b .
 b .
undef_entry:
 push {r0-r12,lr}
 mrs r1,spsr
 sub sp,sp,#8
 str r1,[sp]
 sub r0,lr,#2
 bl fixture_undef
 str r0,[sp,#60]
 ldr r1,[sp]
 msr spsr_cxsf,r1
 add sp,sp,#8
 pop {r0-r12,lr}
 movs pc,lr
'''
    sections=[]
    for i,(s,t) in enumerate(sites):
        sections.extend([(0x635c6000+s-4,'site'+str(i)),(0x635c6000+t,'target'+str(i))])
        asm+=f'.section .site{i},"ax"\n.thumb\npush {{r4,lr}}\ncmp r0,r0\nudf.w #0xa75\npop {{r4,pc}}\n'
        asm+=f'.section .target{i},"ax"\n.thumb\nldr.w ip,1f\nbx ip\n.balign 4\n1: .word original_call\n'
    if a.detail:asm=asm.replace('0xa75','0xa76')
    if a.vfx:asm=asm.replace('0xa75','0xa7f' if a.banks else '0xa7e' if a.repeat else '0xa7d' if a.fast else '0xa7c' if a.full else '0xa7b' if a.grain else '0xa7a' if a.lease else '0xa79' if a.early else '0xa78' if a.frame else '0xa77')
    asm+='.section .note.GNU-stack,"",%progbits\n';(out/'fixture.S').write_text(asm)
    ld='ENTRY(_start)\nSECTIONS {. = 0x40200000; .text : {*(.text.start) *(.text*)} .rodata : {*(.rodata*)} .data : {*(.data*)} .bss (NOLOAD) : {*(.bss*) *(COMMON)}\n'
    ld+=''.join(f'.{n} {x:#x} : {{*(.{n})}}\n' for x,n in sorted(sections))+'}\n';(out/'fixture.ld').write_text(ld)
    sources=['research/capture_multi_test.py','research/capture_multi_harness.c',
        'research/kernel_probe/capture_banks_bridge.S' if a.banks else 'research/kernel_probe/capture_repeat_bridge.S' if a.repeat else 'research/kernel_probe/capture_fast_bridge.S' if a.fast else 'research/kernel_probe/capture_full_bridge.S' if a.full else 'research/kernel_probe/capture_grain_bridge.S' if a.grain else 'research/kernel_probe/capture_lease_bridge.S' if a.lease else 'research/kernel_probe/capture_early_bridge.S' if a.early else 'research/kernel_probe/capture_frame_bridge.S' if a.frame else 'research/kernel_probe/capture_vfx_bridge.S' if a.vfx else 'research/kernel_probe/capture_detail_bridge.S' if a.detail else 'research/kernel_probe/capture_multi_bridge.S']
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a15','-mthumb','-O2','-Wall','-Wextra','-Werror',
        *(['-DTEST_EARLY=1','-DTEST_UDF=0xaa7ff7f0','-DTEST_RETURN=0x7a7f'] if a.banks else ['-DTEST_EARLY=1','-DTEST_UDF=0xaa7ef7f0','-DTEST_RETURN=0x7a7e'] if a.repeat else ['-DTEST_EARLY=1','-DTEST_UDF=0xaa7df7f0','-DTEST_RETURN=0x7a7d'] if a.fast else ['-DTEST_EARLY=1','-DTEST_UDF=0xaa7cf7f0','-DTEST_RETURN=0x7a7c'] if a.full else ['-DTEST_EARLY=1','-DTEST_UDF=0xaa7bf7f0','-DTEST_RETURN=0x7a7b'] if a.grain else ['-DTEST_EARLY=1','-DTEST_UDF=0xaa7af7f0','-DTEST_RETURN=0x7a7a'] if a.lease else ['-DTEST_EARLY=1','-DTEST_UDF=0xaa79f7f0','-DTEST_RETURN=0x7a79'] if a.early else ['-DTEST_VFX=1','-DTEST_UDF=0xaa78f7f0','-DTEST_RETURN=0x7a78'] if a.frame else ['-DTEST_VFX=1','-DTEST_UDF=0xaa77f7f0','-DTEST_RETURN=0x7a77'] if a.vfx else ['-DTEST_UDF=0xaa76f7f0','-DTEST_RETURN=0x7a76'] if a.detail else []),
        '-ffreestanding','-fno-builtin','-nostdlib','-T','fixture.ld','fixture.S',str(ROOT/sources[1]),str(ROOT/sources[2]),'-lgcc','-o','fixture.elf'],cwd=out,check=True)
    run=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults',
        '-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio',
        '-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/fixture.elf,cpu-num=0'],capture_output=True,timeout=15)
    log=run.stdout+run.stderr;(out/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if run.returncode or b'MULTI_CALLBACK_PASSED' not in log or b'FAIL' in log:raise ValueError('Callback fixture failed')
    (out/'proof.json').write_text(json.dumps(dict(avcam_sha256=sha(data),call_sites=pins,
        source_sha256={n:sha((ROOT/n).read_bytes()) for n in sources},log=log.decode(),
        original_instruction_boundaries_verified=True,bridge_and_exception_abi_tested=True,
        native_callees_mocked=True,camera_run=False,pixel_write=False,flash_ready=False),indent=2)+'\n')
if __name__=='__main__':main()
