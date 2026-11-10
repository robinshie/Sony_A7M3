#!/usr/bin/env python3
"""Build and test a reversible native menu-routing experiment, never a flash image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from elf32 import ELF
from creative_dispatch import START, END, VIEW_SHA

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/menu-ram'
LIBS={'ld-linux.so.3':'ld-2.11.2.so','libc.so.6':'libc-2.11.2.so',
      'libdl.so.2':'libdl-2.11.2.so','libcrypt.so.1':'libcrypt-2.11.2.so',
      'librt.so.1':'librt-2.11.2.so','libpthread.so.0':'libpthread-2.11.2.so'}

def run(cmd,**kw):
    return subprocess.run(cmd,check=True,**kw)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def build(usr,sony_root):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    view=ELF(usr/'lib/viewUnified2.so')
    if hashlib.sha256(view.data).hexdigest()!=VIEW_SHA:raise ValueError('Wrong view library')
    run([sys.executable,str(ROOT/'research/creative_dispatch.py'),'--usr',str(usr)],stdout=subprocess.DEVNULL)
    report=json.loads((ROOT/'.lab/creative-research/dispatch-report.json').read_text())
    mapping=report['mappings'][1:98]
    if [r[0] for r in mapping]!=list(range(97)):raise ValueError('Incomplete original dispatch witness')
    (OUT/'dispatch-map.bin').write_bytes(bytes(v for _,style,box in mapping for v in (style,box)))
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/menu_dispatch.S'),'-o','dispatch.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-Ttext=0','-e','ram_dispatch','dispatch.o','-o','dispatch.elf'],cwd=OUT)
    run(['arm-none-eabi-objcopy','-O','binary','-j','.text','dispatch.elf','dispatch.bin'],cwd=OUT)
    symbols=run(['arm-none-eabi-nm','dispatch.elf'],cwd=OUT,capture_output=True,text=True).stdout
    trace=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' trace_pointer')),16)
    patched=(OUT/'dispatch.bin').read_bytes();original=view.read(START,END-START)
    entries=view.read(0xa60998,760)
    if not (trace%4==0 and trace+4==len(patched)<=len(original)):raise ValueError('Unexpected dispatcher layout')
    def array(name,data):return f'static const unsigned char {name}[]={{'+','.join(map(str,data))+'};\n'
    header=f'#define TRACE_OFFSET {trace}\n'+array('original_dispatch',original)+array('patched_dispatch',patched)
    header+='static const uint32_t original_entries[]={'+','.join(map(str,struct.unpack('<190I',entries)))+'};\n'
    (OUT/'menu-ram-data.h').write_text(header)
    (OUT/'original-dispatch.bin').write_bytes(original)
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC','-ffreestanding','-fno-builtin',
           '-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(OUT)]
    if os.environ.get('A7_MENU_DEBUG'):flags.append('-DMENU_DEBUG')
    for action,name in enumerate(('install','inspect','restore')):
        run(['arm-none-eabi-gcc',*flags,f'-DACTION={action}','-c',str(ROOT/'payloads/a7-menu-ram.c'),'-o',f'{name}.o'],cwd=OUT)
        run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',f'{name}.o','-o',f'{name}.so'],cwd=OUT)
    run(['arm-none-eabi-gcc',*flags,'-c',str(ROOT/'research/menu_ram_harness.c'),'-o','harness.o'],cwd=OUT)
    (OUT/'start.S').write_text('''.syntax unified
.arm
.text
.global _start
_start:
    mov fp, #0
    mov lr, #0
    pop {r1}
    mov r2, sp
    push {r2}
    mov r3, #0
    push {r3}
    push {r3}
    ldr r0, =main
    ldr r3, =init
    bl __libc_start_main
    b .
init:
    bx lr
.section .note.GNU-stack,"",%progbits
''')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-c','start.S','-o','start.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-e','_start','--dynamic-linker','/lib/ld-linux.so.3','-z','noexecstack',
         'start.o','harness.o','-L',str(sony_root/'lib'),'-l:libdl-2.11.2.so','-l:libc-2.11.2.so',
         '-l:ld-2.11.2.so','-o','harness'],cwd=OUT)
    lines=['.syntax unified','.arm','.text','bx lr','.section .dispatch,"ax"','.incbin "original-dispatch.bin"',
           '.section .fixture,"aw"','.global synthetic_menu_entries','synthetic_menu_entries:']
    for i,value in enumerate(struct.unpack('<190I',entries)):
        lines.append(f'.word synthetic_menu_entries+{value-0xa60998}' if i%10==0 and value else f'.word {value}')
    root=struct.unpack('<10I',view.read(0xa60c90,40))
    lines+=['.word synthetic_menu_entries,'+','.join(map(str,root[1:])),
            '.org 0xa61c18-0xa60998','.word 0,0','.org 0xa87ce0-0xa60998','.word 0,0,0,0,0,0']
    (OUT/'fixture.S').write_text('\n'.join(lines)+'\n')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-c','fixture.S','-o','fixture.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-shared','-z','noexecstack','--section-start=.dispatch=0x5b98dc',
         '--section-start=.fixture=0xa60998','fixture.o','-o','viewUnified2.so'],cwd=OUT)

def test(kernel,busybox,sony_root):
    with tempfile.TemporaryDirectory(dir=OUT) as directory:
        tmp=Path(directory);fs=tmp/'root'
        for name in ['bin','sony/bin','sony/lib','sony/usr/lib','sony/proc','sony/tmp/jiritsu','sony/dev']:
            (fs/name).mkdir(parents=True,exist_ok=True)
        shutil.copyfile(busybox,fs/'bin/busybox');(fs/'bin/busybox').chmod(0o755)
        musl=busybox.parent.parent/'lib/ld-musl-armhf.so.1'
        if musl.exists():
            (fs/'lib').mkdir();shutil.copy2(musl,fs/'lib/ld-musl-armhf.so.1')
            (fs/'lib/libc.musl-armv7.so.1').symlink_to('ld-musl-armv7.so.1')
        shutil.copyfile(sony_root/'bin/busybox',fs/'sony/bin/busybox');(fs/'sony/bin/busybox').chmod(0o755)
        for name,original in LIBS.items():
            shutil.copyfile(sony_root/'lib'/original,fs/'sony/lib'/name)
            (fs/'sony/lib'/name).chmod(0o755)
        for name in ['install','inspect','restore']:shutil.copyfile(OUT/f'{name}.so',fs/f'sony/tmp/{name}.so')
        shutil.copyfile(OUT/'harness',fs/'sony/tmp/harness');(fs/'sony/tmp/harness').chmod(0o755)
        shutil.copyfile(OUT/'viewUnified2.so',fs/'sony/usr/lib/viewUnified2.so')
        (fs/'init').write_text('''#!/bin/busybox sh
set -eu
b=/bin/busybox
$b mount -t proc proc /sony/proc
printf 'unchanged firmware fixture' > /sony/dev/nflasha15
$b cp /sony/dev/nflasha15 /before
$b chroot /sony /bin/busybox sh -c 'LD_PRELOAD=/tmp/install.so /bin/busybox true'
test "$($b od -An -j8 -N4 -tu4 /sony/tmp/jiritsu/a7menu.bin | $b tr -d ' \\n')" = 0
test "$($b od -An -j44 -N4 -td4 /sony/tmp/jiritsu/a7menu.bin | $b tr -d ' \\n')" = -1
echo QEMU_MENU_ABSENT_REFUSED
$b rm /sony/tmp/jiritsu/a7menu.bin
$b chroot /sony /bin/busybox sh -c 'LD_PRELOAD=/usr/lib/viewUnified2.so /tmp/harness'
$b cmp /before /sony/dev/nflasha15
echo QEMU_MENU_DISK_UNCHANGED
$b poweroff -f
''');(fs/'init').chmod(0o755)
        archive=tmp/'initrd.cpio'
        with archive.open('wb') as f:
            run([shutil.which('bsdtar') or 'tar','-c','--format=newc','-f','-','.'],cwd=fs,stdout=f,
                env={**os.environ,'COPYFILE_DISABLE':'1'})
        cmd=['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','768','-display','none','-serial','stdio',
             '-monitor','none','-nic','none','-no-reboot','-kernel',str(kernel),'-initrd',str(archive),
             '-append','console=ttyAMA0 rdinit=/init quiet panic=1']
        try:r=run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=25)
        except subprocess.TimeoutExpired as e:
            (OUT/'qemu.log').write_bytes(e.stdout or b'');raise
        (OUT/'qemu.log').write_bytes(r.stdout);print(r.stdout.decode(errors='replace'),end='')
        for marker in [b'QEMU_MENU_ABSENT_REFUSED',b'QEMU_MENU_RAM_TESTS_PASSED',b'QEMU_MENU_DISK_UNCHANGED']:
            if marker not in r.stdout:raise ValueError('Missing QEMU witness '+str(marker))
        proof={'payloads':{n:sha(OUT/f'{n}.so') for n in ('install','inspect','restore')},
               'view_sha256':VIEW_SHA,'scope':'RAM menu route only; existing slot 3; no new recipe or firmware write',
               'source_sha256':{n:sha(ROOT/n) for n in ('payloads/a7-menu-ram.c','payloads/a7-runtime-probe.c',
                   'research/menu_dispatch.S','research/menu_ram_harness.c','research/menu_ram.py')}}
        (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('usr','kernel','busybox','sony-root'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();build(a.usr,a.sony_root);test(a.kernel,a.busybox,a.sony_root)
