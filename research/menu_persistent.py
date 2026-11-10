#!/usr/bin/env python3
"""Build an in-place native library patch and test its load-time initialization."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from elf32 import ELF
from creative_dispatch import START, END, VIEW_SHA
from menu_ram import LIBS
from uxc_strings import Strings, RESOURCE

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/menu-persistent'

def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)
def sha(b):return hashlib.sha256(b).hexdigest()

def build(usr):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    view=ELF(usr/'lib/viewUnified2.so')
    if sha(view.data)!=VIEW_SHA:raise ValueError('Wrong original library')
    mapping=json.loads((ROOT/'.lab/creative-research/dispatch-report.json').read_text())
    if mapping['view_sha256']!=VIEW_SHA:raise ValueError('Wrong dispatch witness')
    rows=mapping['mappings'][1:98]
    if [r[0] for r in rows]!=list(range(97)):raise ValueError('Incomplete mappings')
    data=bytes(v for _,style,box in rows for v in (style,box))
    (OUT/'dispatch-map.bin').write_bytes(data)
    (OUT/'map-values.h').write_text(','.join(map(str,data)))
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/menu_persistent.S'),'-o','persistent.o'],cwd=OUT)
    (OUT/'hook.S').write_text('.syntax unified\n.thumb\n.section .hook,"ax"\nb.w recipe_parameters\nbx lr\n.section .note.GNU-stack,"",%progbits\n')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c','hook.S','-o','hook.o'],cwd=OUT)
    run(['arm-none-eabi-ld',f'-Ttext={START:#x}','--section-start=.hook=0x5b9fba','-e','persistent_init','persistent.o','hook.o','-o','patch.elf'],cwd=OUT)
    run(['arm-none-eabi-objcopy','-O','binary','-j','.text','patch.elf','patch.bin'],cwd=OUT)
    patch=(OUT/'patch.bin').read_bytes()
    if len(patch)>END-START or len(patch)%2:raise ValueError('Patch exceeds original function')
    symbols={row.split()[-1]:int(row.split()[0],16) for row in run(['arm-none-eabi-nm','patch.elf'],cwd=OUT,capture_output=True,text=True).stdout.splitlines() if len(row.split())==3}
    patched=bytearray(view.data)
    def offset(va):
        for kind,off,base,_,size,*_ in view.segments:
            if kind==1 and base<=va<base+size:return off+va-base
        raise ValueError('Not file-backed')
    at=offset(START)
    patched[at:at+len(patch)]=patch
    patched[at+len(patch):offset(END)]=b'\x00\xbf'*((END-START-len(patch))//2)
    hook=ELF(OUT/'patch.elf').read(0x5b9fba,4)
    if view.read(0x5b9fba,4)!=bytes.fromhex('bb682146'):raise ValueError('Wrong parameter hook preimage')
    patched[offset(0x5b9fba):offset(0x5b9fba)+4]=hook
    dyn=next(s for s in view.sections if s[1]==6)
    init_offsets=[p for p in range(dyn[4],dyn[4]+dyn[5],8) if struct.unpack_from('<I',patched,p)[0]==12]
    if len(init_offsets)!=1 or struct.unpack_from('<I',patched,init_offsets[0]+4)[0]!=0x157819:
        raise ValueError('Unexpected initializer')
    struct.pack_into('<I',patched,init_offsets[0]+4,symbols['persistent_init']|1)
    (OUT/'viewUnified2.so').write_bytes(patched)
    for locale,text in [('simplifiedchinese','复古衣橱'),('english','Retro Wardrobe')]:
        original=(usr/f'share/app/string_{locale}.uxc').read_bytes()
        (OUT/f'string_{locale}.uxc').write_bytes(Strings(original).add(text))
    # File-backed table and normal ELF relocations, as used by Sony's loader.
    entries=struct.unpack('<190I',view.read(0xa60998,760))
    lines=['.syntax unified','.section .fixture,"aw"','.global synthetic_menu_entries','synthetic_menu_entries:']
    for i,v in enumerate(entries):
        lines.append(f'.word synthetic_menu_entries+{v-0xa60998}' if i%10==0 and v else f'.word {v}')
    root=struct.unpack('<10I',view.read(0xa60c90,40))
    lines+=['.word synthetic_menu_entries,'+','.join(map(str,root[1:])),'.global old_init_calls','old_init_calls: .word 0',
            '.section .old_init,"ax"','.thumb','.thumb_func','old_init:',
            'ldr r0, 1f','0: add r0, pc','ldr r1,[r0]','adds r1,#1','str r1,[r0]','bx lr','.balign 4',
            '1: .word old_init_calls-(0b+4)',
            '.section .get_id,"ax"','.arm','ldr r0,[r0]','bx lr',
            '.section .testtext,"ax"','.thumb','.global test_parameters','.thumb_func','test_parameters:',
            'push {r4,r7,lr}','sub sp,#4','mov r4,r0','mov r7,r1','bl 0x5b9fba','mov r0,r3',
            'add sp,#4','pop {r4,r7,pc}', '.section .note.GNU-stack,"",%progbits']
    (OUT/'fixture.S').write_text('\n'.join(lines)+'\n')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c','fixture.S','-o','fixture.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-shared','-Bsymbolic','-z','noexecstack','-init','persistent_init',f'-Ttext={START:#x}',
         '--section-start=.fixture=0xa60998','--section-start=.old_init=0x157818',
         '--section-start=.get_id=0x15ed04','--section-start=.hook=0x5b9fba','--section-start=.testtext=0x100000',
         'persistent.o','hook.o','fixture.o','-o','fixture.so'],cwd=OUT)
    return {'view_sha256':VIEW_SHA,'patch_size':len(patch),'init_file_offset':init_offsets[0]+4,
            'init_va':symbols['persistent_init']|1,'resource_id':RESOURCE,
            'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in ('research/menu_persistent.S',
                'research/menu_persistent.py','research/menu_persistent_harness.c','research/uxc_strings.py')},
            'files':{n:sha((OUT/n).read_bytes()) for n in ('viewUnified2.so','string_simplifiedchinese.uxc','string_english.uxc')}}

def test(kernel,busybox,sony_root):
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector',
           '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(OUT)]
    run(['arm-none-eabi-gcc',*flags,'-c',str(ROOT/'research/menu_persistent_harness.c'),'-o','harness.o'],cwd=OUT)
    shutil.copyfile(ROOT/'.lab/menu-ram/start.S',OUT/'start.S')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-c','start.S','-o','start.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-e','_start','--dynamic-linker','/lib/ld-linux.so.3','-z','noexecstack',
         'start.o','harness.o','-L',str(sony_root/'lib'),'-l:libdl-2.11.2.so','-l:libc-2.11.2.so',
         '-l:ld-2.11.2.so','-o','harness'],cwd=OUT)
    with tempfile.TemporaryDirectory(dir=OUT) as temp:
        fs=Path(temp)/'root'
        for name in ['bin','lib','sony/bin','sony/lib','sony/tmp']:(fs/name).mkdir(parents=True,exist_ok=True)
        shutil.copy2(busybox,fs/'bin/busybox');(fs/'bin/busybox').chmod(0o755)
        musl=busybox.parent.parent/'lib/ld-musl-armhf.so.1'
        if musl.exists():
            shutil.copy2(musl,fs/'lib/ld-musl-armhf.so.1');(fs/'lib/libc.musl-armv7.so.1').symlink_to('ld-musl-armhf.so.1')
        shutil.copy2(sony_root/'bin/busybox',fs/'sony/bin/busybox');(fs/'sony/bin/busybox').chmod(0o755)
        for name,original in LIBS.items():
            shutil.copy2(sony_root/'lib'/original,fs/'sony/lib'/name);(fs/'sony/lib'/name).chmod(0o755)
        for name in ['fixture.so','harness']:
            shutil.copyfile(OUT/name,fs/'sony/tmp'/name);(fs/'sony/tmp'/name).chmod(0o755)
        (fs/'init').write_text('#!/bin/busybox sh\nset -eu\n/bin/busybox chroot /sony /bin/busybox sh -c "LD_PRELOAD=/tmp/fixture.so /tmp/harness"\n/bin/busybox poweroff -f\n')
        (fs/'init').chmod(0o755)
        archive=Path(temp)/'initrd.cpio'
        with archive.open('wb') as stream:
            run([shutil.which('bsdtar') or 'tar','-c','--format=newc','-f','-','.'],cwd=fs,stdout=stream,
                env={**os.environ,'COPYFILE_DISABLE':'1'})
        r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','768','-display','none','-serial','stdio',
               '-monitor','none','-nic','none','-no-reboot','-kernel',str(kernel),'-initrd',str(archive),
               '-append','console=ttyAMA0 rdinit=/init quiet panic=1'],capture_output=True,timeout=25)
        (OUT/'qemu.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(errors='replace'),end='')
        if b'QEMU_PERSISTENT_MENU_PASSED' not in r.stdout or b'FAIL ' in r.stdout:raise ValueError('Persistent menu test failed')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('usr','kernel','busybox','sony-root'):cli.add_argument('--'+name,required=True,type=Path)
    args=cli.parse_args();proof=build(args.usr);test(args.kernel,args.busybox,args.sony_root)
    proof['scope']='Initializer, original menu mappings and recipe parameters under Sony glibc; no sensor/ISP emulation'
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
