#!/usr/bin/env python3
"""Build v3 over verified v2; test original ARM cursor/Fn selection paths."""
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
from creative_dispatch import VIEW_SHA, CONFIG_SHA
from menu_ram import LIBS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/menu-identity'
IDENTITY=0x5b9a60
HOOKS={0x5bb18e:bytes.fromhex('fef7effc'),0x5bb9de:bytes.fromhex('fef7c7f8')}
LABEL=0x8359f0
FN_SHA='5dba5a3e036e40b7d852af47cef917ee2a5b11bc100b901ff51207e527b32667'
def sha(b):return hashlib.sha256(b).hexdigest()
def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)

def build(usr):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    view=ELF(usr/'lib/viewUnified2.so');config=ELF(usr/'lib/CautionConfig.so');fn=ELF(usr/'lib/viewUnified4.so')
    if sha(view.data)!=VIEW_SHA or sha(config.data)!=CONFIG_SHA or sha(fn.data)!=FN_SHA:raise ValueError('Wrong original 4.04 inputs')
    previous=ROOT/'.lab/creative-v2'
    manifest=json.loads((previous/'manifest.json').read_text())
    old=(previous/'viewUnified2.so').read_bytes()
    if sha(old)!=manifest['files']['/lib/viewUnified2.so']['after_sha256']:raise ValueError('Wrong v2 preimage')
    prior=json.loads((ROOT/'.lab/menu-lazy/proof.json').read_text())
    for path,digest in prior['source_sha256'].items():
        if sha((ROOT/path).read_bytes())!=digest:raise ValueError('Stale v2 source: '+path)
    # The helper uses only space already reclaimed and NOP-filled by v2.
    if prior['patch_size']!=IDENTITY-0x5b98dc or old[IDENTITY:0x5b9b6e]!=b'\x00\xbf'*135:
        raise ValueError('Unexpected v2 code space')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/menu_identity.S'),'-o','patch.o'],cwd=OUT)
    locations=['--section-start=.identity=0x5b9a60','--section-start=.remember=0x5bb18e','--section-start=.reopen=0x5bb9de']
    run(['arm-none-eabi-ld',*locations,'-e','recipe_reverse','patch.o','-o','patch.elf'],cwd=OUT)
    patch=ELF(OUT/'patch.elf')
    identity=next(s for s in patch.sections if s[3]==IDENTITY)
    size=identity[5]
    if size>270:raise ValueError('Helper exceeds proven unused space')
    edited=bytearray(old);edited[IDENTITY:IDENTITY+size]=patch.read(IDENTITY,size)
    for address,before in HOOKS.items():
        if view.read(address,4)!=before or old[address:address+4]!=before:raise ValueError('Hook preimage mismatch')
        edited[address:address+4]=patch.read(address,4)
    (OUT/'viewUnified2.so').write_bytes(edited)
    c=bytearray(config.data)
    if config.word(LABEL)!=0x0204e08d:raise ValueError('Wrong slot 3 Neutral text')
    struct.pack_into('<I',c,LABEL,0x0204ed84)
    (OUT/'CautionConfig.so').write_bytes(c)
    # Original Fn list order and property records are local Sony inputs.
    values=[]
    for at in range(0x9a780c,0x9a780c+91*4,4):
        name=config.relocations[at][1]['name'].replace('cmnViewSettingNode','cmnViewSettingPropertyList',1)
        sym=config.symbols[name]
        if sym['size']!=120:raise ValueError('Unexpected Fn property size')
        values.append(struct.unpack_from('<30I',c,sym['value']))
    (OUT/'fn-properties.h').write_text('\n'.join('{'+','.join(map(str,row))+'},' for row in values)+'\n')
    blobs={'reverse.bin':view.read(0x5b9b70,0xf0),'tables.bin':view.read(0x7aa168,0x90),
           'fn-select.bin':fn.read(0x197d78,0x104),'fn-map.bin':fn.read(0x19a0fc,0x2e8)}
    for n,b in blobs.items():(OUT/n).write_bytes(b)
    (OUT/'fixture.S').write_text('''.syntax unified
.section .reverse,"ax"
.thumb
.global stock_reverse
.thumb_func
stock_reverse: .incbin "reverse.bin"
.section .tables,"a"
.incbin "tables.bin"
.section .fnselect,"ax"
.incbin "fn-select.bin",0,0x24
.global original_fn_select
.thumb_func
original_fn_select: .incbin "fn-select.bin",0x24
.section .fnmap,"ax"
.global original_fn_map
.thumb_func
original_fn_map: .incbin "fn-map.bin"
.section .cursor,"ax"
.arm
ldr r3,[r0]
add r3,r3,#1
str r3,[r0]
str r1,[r0,#4]
bx lr
.section .test,"ax"
.thumb
.global test_remember
.thumb_func
test_remember: push {r3,lr}
b.w 0x5bb18e
.global test_reopen
.thumb_func
test_reopen: push {r3,lr}
b.w 0x5bb9de
.section .remember_return,"ax"
pop {r3,pc}
.section .reopen_return,"ax"
pop {r3,pc}
.section .note.GNU-stack,"",%progbits
''')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c','fixture.S','-o','fixture.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-shared','-Bsymbolic','-z','noexecstack',*locations,
         '--section-start=.reverse=0x5b9b70','--section-start=.tables=0x7aa168',
         '--section-start=.fnselect=0x197d78','--section-start=.fnmap=0x19a0fc',
         '--section-start=.cursor=0x15e118','--section-start=.test=0x100000',
         '--section-start=.remember_return=0x5bb192','--section-start=.reopen_return=0x5bb9e2',
         'patch.o','fixture.o','-o','fixture.so'],cwd=OUT)
    sources=('research/menu_identity.S','research/menu_identity.py','research/menu_identity_harness.c',
             'research/elf32.py','research/menu_ram.py','research/creative_dispatch.py',*prior['source_sha256'])
    return {'previous_view_sha256':sha(old),'config_sha256':CONFIG_SHA,'fn_sha256':sha(fn.data),
            'helper_va':IDENTITY,'helper_size':size,'init_file_offset':0x5bb9de,
            'hooks':{hex(a):{'before':b.hex(),'after':patch.read(a,4).hex()} for a,b in HOOKS.items()},
            'label_va':LABEL,'scope':'Original ARM cursor/Fn routing with UI fixtures; no sensor/ISP emulation',
            'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in sources},
            'files':{n:sha((OUT/n).read_bytes()) for n in ('viewUnified2.so','CautionConfig.so')}}

def test(kernel,busybox,sony_root):
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-ffreestanding','-fno-builtin',
           '-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(OUT)]
    run(['arm-none-eabi-gcc',*flags,'-c',str(ROOT/'research/menu_identity_harness.c'),'-o','harness.o'],cwd=OUT)
    shutil.copyfile(ROOT/'.lab/menu-ram/start.S',OUT/'start.S')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-c','start.S','-o','start.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-e','_start','--dynamic-linker','/lib/ld-linux.so.3','-z','noexecstack',
         'start.o','harness.o','-L',str(sony_root/'lib'),'-l:libdl-2.11.2.so','-l:libc-2.11.2.so','-l:ld-2.11.2.so','-o','harness'],cwd=OUT)
    with tempfile.TemporaryDirectory(dir=OUT) as temporary:
        fs=Path(temporary)/'root'
        for n in ('bin','lib','sony/bin','sony/lib','sony/tmp'):(fs/n).mkdir(parents=True,exist_ok=True)
        for src,dst in ((busybox,fs/'bin/busybox'),(sony_root/'bin/busybox',fs/'sony/bin/busybox')):
            shutil.copy2(src,dst);dst.chmod(0o755)
        musl=busybox.parent.parent/'lib/ld-musl-armhf.so.1'
        if musl.exists():
            shutil.copy2(musl,fs/'lib/ld-musl-armhf.so.1');(fs/'lib/libc.musl-armv7.so.1').symlink_to('ld-musl-armhf.so.1')
        for name,original in LIBS.items():
            shutil.copy2(sony_root/'lib'/original,fs/'sony/lib'/name);(fs/'sony/lib'/name).chmod(0o755)
        for name in ('fixture.so','harness'):
            shutil.copy2(OUT/name,fs/'sony/tmp'/name);(fs/'sony/tmp'/name).chmod(0o755)
        (fs/'init').write_text('#!/bin/busybox sh\nset -eu\n/bin/busybox chroot /sony /bin/busybox sh -c "LD_PRELOAD=/tmp/fixture.so /tmp/harness"\n/bin/busybox poweroff -f\n')
        (fs/'init').chmod(0o755)
        archive=Path(temporary)/'initrd.cpio'
        with archive.open('wb') as stream:
            run([shutil.which('bsdtar') or 'tar','-c','--format=newc','-f','-','.'],cwd=fs,stdout=stream,env={**os.environ,'COPYFILE_DISABLE':'1'})
        r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','768','-display','none','-serial','stdio',
               '-monitor','none','-nic','none','-no-reboot','-kernel',str(kernel),'-initrd',str(archive),
               '-append','console=ttyAMA0 rdinit=/init quiet panic=1'],capture_output=True,timeout=25)
        (OUT/'qemu.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(errors='replace'),end='')
        if b'QEMU_IDENTITY_PASSED' not in r.stdout or b'FAIL ' in r.stdout:raise ValueError('Identity tests failed')

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('usr','kernel','busybox','sony-root'):cli.add_argument('--'+name,type=Path,required=True)
    args=cli.parse_args();proof=build(args.usr);test(args.kernel,args.busybox,args.sony_root)
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
