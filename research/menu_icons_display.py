#!/usr/bin/env python3
"""Repair the actual belt/footer paths, exercising Sony ARM display routines."""
import argparse
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

from elf32 import ELF
import menu_icons
import menu_lazy
import menu_identity
from style_icons import Images

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/menu-icons-display'
sha=menu_lazy.sha
run=menu_lazy.run
LOCATIONS={'.footer':0x5b9acc,'.displayhook':0x5b9e36,'.count':0x5bb998}

def build(usr):
    previous=ROOT/'.lab/creative-icons-list'
    manifest=json.loads((previous/'manifest.json').read_text())
    old=(previous/'viewUnified2.so').read_bytes()
    if sha(old)!=manifest['files']['/lib/viewUnified2.so']['after_sha256']:
        raise ValueError('Wrong deployed view preimage')
    prior=ROOT/'.lab/style-icons-list/proof.json'
    if sha(prior.read_bytes())!=manifest['native_proof_sha256']:
        raise ValueError('Previous proof changed')
    inherited=json.loads(prior.read_text())['source_sha256']
    for path,digest in inherited.items():
        if sha((ROOT/path).read_bytes())!=digest:raise ValueError('Changed prior source: '+path)
    image=(previous/'image_cmn_43.uxc').read_bytes()
    if sha(image)!=manifest['files']['/share/app/image_cmn_43.uxc']['after_sha256']:
        raise ValueError('Wrong installed images')
    images=Images(image)
    if images.pixels(0x5c823)[:2]!=images.pixels(0x5c865)[:2] or images.pixels(0x5c823)[:2]!=(70,60):
        raise ValueError('Footer resources must have identical dimensions')
    if struct.unpack_from('<II',old,0x5b9ac4)!=(0x0205c049,0x0205c04a):
        raise ValueError('Wrong prior icon references')
    if old[0x5b9acc:0x5b9b6e]!=b'\0\xbf'*81:
        raise ValueError('Helper space is not unused')
    expected={0x5b9e36:bytes.fromhex('0bf1ff31'),0x5bb998:bytes.fromhex('a0f1060c')}
    for at,b in expected.items():
        if old[at:at+4]!=b:raise ValueError('Wrong display hook preimage')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/menu_icons_display.S'),'-o','patch.o'],cwd=OUT)
    run(['arm-none-eabi-ld',*[f'--section-start={s}={a:#x}' for s,a in LOCATIONS.items()],
         '-e','recipe_footer','patch.o','-o','patch.elf'],cwd=OUT)
    elf=ELF(OUT/'patch.elf');new=bytearray(old)
    struct.pack_into('<II',new,0x5b9ac4,0x0205c87e,0x0205c823)
    for section,address in LOCATIONS.items():
        length=next(s[5] for s in elf.sections if s[3]==address)
        if length>(0x5b9b6e-address if section=='.footer' else 4):raise ValueError('Patch exceeds bounds')
        new[address:address+length]=elf.read(address,length)
    (OUT/'viewUnified2.so').write_bytes(new)
    (OUT/'image_cmn_43.uxc').write_bytes(image)
    # Reproduce the old native fixtures without invalidating deployed proofs.
    proof_path=ROOT/'.lab/menu-icons/proof.json';saved=proof_path.read_bytes()
    try:menu_icons.build(usr)
    finally:proof_path.write_bytes(saved)
    for kind in ('lazy','identity'):
        directory=OUT/kind;directory.mkdir(exist_ok=True)
        for source in (ROOT/'.lab/menu-icons'/kind).iterdir():
            if source.suffix in ('.bin','.h','.S'):shutil.copy2(source,directory/source.name)
        (directory/'body.bin').write_bytes(new[0x5b98dc:0x5b9b6e])
        locations=['--section-start=.body=0x5b98dc']
        if kind=='identity':
            locations += ['--section-start=.remember=0x5bb18e','--section-start=.reopen=0x5bb9de',
                '--section-start=.reverse=0x5b9b70','--section-start=.tables=0x7aa168',
                '--section-start=.fnselect=0x197d78','--section-start=.fnmap=0x19a0fc',
                '--section-start=.cursor=0x15e118','--section-start=.test=0x100000',
                '--section-start=.remember_return=0x5bb192','--section-start=.reopen_return=0x5bb9e2']
        else:
            locations += ['--section-start=.hook=0x5b9fba','--section-start=.viewhook=0x5bb266',
                '--section-start=.fixture=0xa60998','--section-start=.original_init=0x40bbec',
                '--section-start=.get_id=0x15ed04','--section-start=.testtext=0x100000']
            additions=['.syntax unified']
            blobs={'display':(0x5b9c60,0x260,'native_display'),
                   'combo':(0x56a334,0x94,'native_combo_select'),
                   'count':(0x5bb998,4,'native_count')}
            for name,(at,length,symbol) in blobs.items():
                (directory/(name+'.bin')).write_bytes(new[at:at+length])
                additions += [f'.section .{name},"ax"','.thumb',f'.global {symbol}',
                    '.thumb_func',symbol+':',f'.incbin "{name}.bin"']
                if name=='count':additions+=['mov r0,ip','bx lr']
                locations.append(f'--section-start=.{name}={at:#x}')
            # Only external GUI side effects are mocked. Both native display
            # routing and native array lookup/setImage run unchanged in QEMU.
            proxies={'widget':(0x158768,0,'arm'),'image':(0x15be60,1,'arm'),
                     'index':(0x583242,2,'thumb'),'parameter':(0x5ab7d4,3,'thumb')}
            for name,(at,index,mode) in proxies.items():
                additions += [f'.section .{name},"ax"','.'+mode]
                if mode=='arm':
                    additions += ['ldr ip,1f','0: add ip,pc',f'ldr ip,[ip,#{index*4}]','bx ip',
                                  '.balign 4','1: .word display_callbacks-(0b+8)']
                else:
                    additions += ['ldr.w ip,1f','0: add ip,pc',f'ldr.w ip,[ip,#{index*4}]','bx ip',
                                  '.balign 4','1: .word display_callbacks-(0b+4)']
                locations.append(f'--section-start=.{name}={at:#x}')
            for name,at,mode,n in [('casticon',0x15844c,'arm',1),('castcombo',0x56a54c,'thumb',1),
                    ('castparam',0x5ab67c,'thumb',1),('size',0x15abf4,'arm',1)]:
                additions += [f'.section .{name},"ax"','.'+mode]+['bx lr']*n
                locations.append(f'--section-start=.{name}={at:#x}')
            # The PLT has a Thumb tail-call entry and a separate ARM BLX entry.
            additions += ['.section .dispon,"ax"','.thumb','bx lr','nop','.arm','bx lr']
            locations.append('--section-start=.dispon=0x15c608')
            additions += ['.data','.balign 4','.global display_callbacks','display_callbacks: .word 0,0,0,0']
            with (directory/'fixture.S').open('a') as f:f.write('\n'+'\n'.join(additions)+'\n')
        for name in ('body','fixture'):
            run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',name+'.S','-o',name+'.o'],cwd=directory)
        run(['arm-none-eabi-ld','-shared','-Bsymbolic','-z','noexecstack',*locations,
             'body.o','fixture.o','-o','fixture.so'],cwd=directory)
    source=dict(inherited)
    for name in ('menu_icons_display.py','menu_icons_display.S','menu_icons_display_harness.c'):
        p='research/'+name;source[p]=sha((ROOT/p).read_bytes())
    for p in ('payloads/a7-display-inspect.c','payloads/a7-runtime-probe.c'):
        source[p]=sha((ROOT/p).read_bytes())
    return {'scope':'Belt references and footer resource routing; original model indices and recipe retained',
        'previous_view_sha256':sha(old),'icon_sha256':sha(image),
        'init_file_offset':0x5b9e36,'source_sha256':source,
        'files':{n:sha((OUT/n).read_bytes()) for n in ('viewUnified2.so','image_cmn_43.uxc')}}

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('usr','kernel','busybox','sony-root'):cli.add_argument('--'+name,type=Path,required=True)
    a=cli.parse_args();proof=build(a.usr)
    original_run=menu_lazy.run
    def display_harness(cmd,**kw):
        cmd=[str(ROOT/'research/menu_icons_display_harness.c') if x==str(ROOT/'research/menu_lazy_harness.c') else x for x in cmd]
        if cmd[0]=='qemu-system-arm' and os.environ.get('A7M3_TRACE_DISPLAY'):
            cmd+=['-d','in_asm','-D',str(OUT/'trace.log')]
            kw['timeout']=8
        try:return original_run(cmd,**kw)
        except subprocess.TimeoutExpired as error:
            (OUT/'lazy/qemu-failed.log').write_bytes((error.stdout or b'')+(error.stderr or b''))
            print((error.stdout or b'').decode(errors='replace'))
            raise
    menu_lazy.OUT=OUT/'lazy';menu_lazy.run=display_harness
    menu_lazy.test(a.kernel,a.busybox,a.sony_root)
    if b'QEMU_RW_DISPLAY_PASSED' not in (OUT/'lazy/qemu.log').read_bytes():raise ValueError('Display tests missing')
    menu_identity.OUT=OUT/'identity';menu_identity.test(a.kernel,a.busybox,a.sony_root)
    proof['qemu_logs']={n:sha((OUT/n/'qemu.log').read_bytes()) for n in ('lazy','identity')}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
