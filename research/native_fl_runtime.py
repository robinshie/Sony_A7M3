#!/usr/bin/env python3
"""Execute libbackup wrappers, the kernel write body and resident FL core offline.

OSAL transport, kernel data access/locks/copy/callbacks are modeled. No USB,
filesystem persistence, live menu scheduling, or camera writes are performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

from elf32 import ELF

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-fl-runtime'
LIB_SHA='b6420f8f7cacade524e1ba7c5b0d8b06691c22ed793dca084fdf1c1d9ae092f3'
KERNEL_SHA='2d26bbdfdf06c53b5ce4caac438484bad8e1f4205cd9cdbab71531115790167e'
LIB_BASE=0x40300000
KERNEL_BASE=0x40400000
WRAPPERS={'size':(0x1174,0x11a4),'attr':(0x11d4,0x1204),
          'read':(0x1204,0x1234),'write':(0x1358,0x1388),
          'sync_subsystem':(0x14f0,0x151c),'sync_all':(0x151c,0x1544)}


def sha(data):return hashlib.sha256(data).hexdigest()


def kernel_sections(data):
    h=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    if h[0][:6]!=b'\x7fELF\x01\x01' or h[1:3]!=(1,40):raise ValueError('Expected ARM relocatable kernel module')
    sections=[struct.unpack_from('<10I',data,h[6]+i*h[11]) for i in range(h[12])]
    def content(s):return data[s[4]:s[4]+s[5]]
    names=content(sections[h[13]])
    def string(table,at):return table[at:table.index(b'\0',at)].decode()
    named={string(names,s[0]):(i,s) for i,s in enumerate(sections)}
    text_index,text_section=named['.text'];symbols={};relocations={}
    for i,s in enumerate(sections):
        if s[1]!=2:continue
        strings=content(sections[s[6]]);entries=[]
        for at in range(s[4],s[4]+s[5],s[9]):
            name,value,size,info,other,section=struct.unpack_from('<IIIBBH',data,at)
            name=string(strings,name)
            if not name and section: name=string(names,sections[section][0])
            entries.append((name,value,size,section))
        symbols[i]=entries
    for s in sections:
        if s[1]!=9 or s[7]!=text_index:continue
        for at in range(s[4],s[4]+s[5],s[9]):
            address,info=struct.unpack_from('<II',data,at)
            relocations[address]=(info&255,symbols[s[6]][info>>8])
    return content(text_section),relocations,content(named['.rodata.str1.1'][1])


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usr',required=True,type=Path)
    p.add_argument('--bundle',required=True,type=Path,help='Private native-fl-01 bundle with original/candidate LUT')
    args=p.parse_args()
    lib=ELF(args.usr/'lib/libbackup.so');kernel=(args.usr/'kmod/backup.ko').read_bytes()
    if sha(lib.data)!=LIB_SHA or sha(kernel)!=KERNEL_SHA:raise ValueError('Requires pinned A7M3 4.04 backup inputs')
    originals=(args.bundle/'00030004.bin').read_bytes();candidate=(args.bundle/'candidate.bin').read_bytes()
    if len(originals)!=1280 or len(candidate)!=1280:raise ValueError('LUT lengths')
    OUT.mkdir(mode=0o700,parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    text,relocations,strings=kernel_sections(kernel)
    (OUT/'kernel-text.bin').write_bytes(text);(OUT/'kernel-strings.bin').write_bytes(strings)
    codec=(args.bundle/'codec.bin').read_bytes()
    if len(codec)!=771:raise ValueError('Coordinate codec length')
    other=b''.join((args.bundle/f'{p:08x}.bin').read_bytes() for p in range(0x30005,0x30008))
    if len(other)!=3840:raise ValueError('Other LUT lengths')
    (OUT/'tables.bin').write_bytes(originals+candidate+codec+b'\0'+other)
    asm='.syntax unified\n';placements=[];ranges={};applied=[]
    for name,(a,b) in WRAPPERS.items():
        blob=lib.read(a,b-a);(OUT/f'{name}.bin').write_bytes(blob)
        asm+=f'.section .lib_{name},"ax"\n.incbin "{name}.bin"\n'
        placements.append((LIB_BASE+a,'lib_'+name));ranges['lib_'+name]=[hex(a),b-a,sha(blob)]
    asm+='''.section .rpc,"ax"
.arm
ldr ip,1f
bx ip
1: .word fake_rpc
'''
    placements.append((LIB_BASE+0xda8,'rpc'))
    mocks={'Data_GetHeader':'mock_header','rt_down_write':'mock_lock','rt_up_write':'mock_unlock',
           'Data_SearchId':'mock_search','Data_GetAttr':'mock_attr','Data_GetID1':'mock_id1',
           'Data_GetVmaxSize':'mock_vmax','Data_GetSize':'mock_size',
           'Data_GetDataSizePt':'mock_size_ptr','Data_GetDataPt':'mock_data',
           '__copy_from_user':'mock_copy_user','__memzero':'mock_zero','memcpy':'mock_copy',
           'backup_sharedcb_send_msg':'mock_notify','backup_logrec':'mock_log'}
    for name,a,b in (('kernel_write',0x5ec,0x888),('kernel_entry',0x167c,0x1694)):
        ranges[name]=[hex(a),b-a,sha(text[a:b])]
        asm+=f'.section .{name},"ax"\n.arm\n';cursor=a
        for off,(kind,symbol) in sorted(relocations.items()):
            if not a<=off<b:continue
            if cursor<off:asm+=f'.incbin "kernel-text.bin",{cursor},{off-cursor}\n'
            sym=symbol[0]
            if kind==28 and sym in mocks:asm+='bl '+mocks[sym]+'\n'
            elif kind==2 and sym=='backup_rwlock':asm+='.word mock_locks\n'
            elif kind==2 and sym=='.rodata.str1.1':
                addend=struct.unpack_from('<I',text,off)[0];asm+=f'.word kernel_strings+{addend}\n'
            else:raise ValueError(f'Unhandled kernel relocation {off:#x} {kind} {sym}')
            applied.append({'offset':hex(off),'type':kind,'symbol':sym});cursor=off+4
        if cursor<b:asm+=f'.incbin "kernel-text.bin",{cursor},{b-cursor}\n'
        placements.append((KERNEL_BASE+a,name))
    asm+='''.section .kernel_strings,"a"
.global kernel_strings
kernel_strings: .incbin "kernel-strings.bin"
.section .tables,"a"
.incbin "tables.bin"
.section .note.GNU-stack,"",%progbits
'''
    placements.extend(((0x40500000,'kernel_strings'),(0x40600000,'tables')))
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
    ld+=''.join(f'.{name} {address:#x} : {{ *(.{name}) }}\n' for address,name in sorted(placements))+'}\n'
    (OUT/'guest.ld').write_text(ld)
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-fstack-usage',
           '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
           '-I',str(ROOT/'payloads')]
    subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','guest.ld','start.S','native.S',
                    str(ROOT/'research/native_fl_runtime_harness.c'),str(ROOT/'payloads/a7-fl-runtime.c'),
                    str(ROOT/'payloads/a7-fl-runtime-prefs.c'),
                    str(ROOT/'payloads/a7-fl-runtime-control.c'),
                    str(ROOT/'payloads/a7-fl-runtime-recovery.c'),
                    '-lgcc','-o','runtime-test.elf'],cwd=OUT,check=True)
    subprocess.run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/'payloads/a7-fl-runtime.c'),
                    '-o','runtime.o'],cwd=OUT,check=True)
    subprocess.run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/'payloads/a7-fl-runtime-prefs.c'),
                    '-o','prefs.o'],cwd=OUT,check=True)
    subprocess.run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/'payloads/a7-fl-runtime-control.c'),
                    '-o','control.o'],cwd=OUT,check=True)
    subprocess.run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/'payloads/a7-fl-runtime-recovery.c'),
                    '-o','recovery.o'],cwd=OUT,check=True)
    subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-shared','-Wl,--no-undefined,-z,noexecstack','runtime.o','prefs.o','control.o','recovery.o','-lgcc',
                    '-o','liba7-fl-runtime.so'],cwd=OUT,check=True)
    r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-smp','1','-m','1024',
                      '-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none',
                      '-serial','stdio','-semihosting-config','enable=on,target=native','-device',
                      f'loader,file={OUT}/runtime-test.elf,cpu-num=0'],capture_output=True,timeout=30)
    log=r.stdout+r.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if r.returncode or b'NATIVE_FL_RUNTIME_PASSED' not in r.stdout or b'FAIL ' in log:raise ValueError('Native runtime test failed')
    sources=('payloads/a7-fl-runtime.h','payloads/a7-fl-runtime.c','payloads/a7-fl-runtime-prefs.h',
             'payloads/a7-fl-runtime-prefs.c','payloads/a7-fl-runtime-control.h','payloads/a7-fl-runtime-control.c',
             'payloads/a7-fl-runtime-recovery.h','payloads/a7-fl-runtime-recovery.c',
             'payloads/a7-fl-color.h','research/native_fl_runtime.py','research/native_fl_runtime_harness.c')
    proof={'libbackup_sha256':LIB_SHA,'kernel_backup_sha256':KERNEL_SHA,
           'ranges':ranges,'applied_kernel_relocations':applied,
           'source_sha256':{s:sha((ROOT/s).read_bytes()) for s in sources},
           'files_sha256':{s:sha((OUT/s).read_bytes()) for s in ('runtime-test.elf','liba7-fl-runtime.so','tables.bin','qemu.log')},
           'original_lut_sha256':sha(originals),'candidate_lut_sha256':sha(candidate),'codec_sha256':sha(codec),
           'scope':'Original libbackup argument/result wrappers + original kernel fixed-size write; OSAL/kernel services modeled; resident toggle tested against this fixture',
           'native_write_abi_proven':True,'explicit_sync_called_by_runtime':False,
           'camera_integration':False,'preference_record_codec_verified':True,'durable_preference_io_verified':False,
           'exact_generated_family_recovery_verified':True,'preview_commit_separation_verified':True,
           'autosave_interception_implemented':False,'flash_ready':False}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')


if __name__=='__main__':main()
