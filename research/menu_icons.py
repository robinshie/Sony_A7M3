#!/usr/bin/env python3
"""Build RW icon correction over exact v3; exercise native ARM UI paths."""
import argparse
import json
import shutil
from pathlib import Path
from elf32 import ELF
import menu_lazy
import menu_identity
from style_icons import Images, patch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/menu-icons'
sha=menu_lazy.sha
run=menu_lazy.run
ICON_SHA='5cb0f3c26de5923674473ae91877960b8b01d42e573767b46d6f25bf376d2db0'

def build(usr):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'proof.json').unlink(missing_ok=True)
    prior=json.loads((ROOT/'.lab/creative-v3/manifest.json').read_text())
    previous=ROOT/'.lab/creative-v3/viewUnified2.so'
    old=previous.read_bytes()
    if sha(old)!=prior['files']['/lib/viewUnified2.so']['after_sha256']: raise ValueError('Wrong v3 preimage')
    for directory in ('menu-lazy','menu-identity'):
        proof=json.loads((ROOT/'.lab'/directory/'proof.json').read_text())
        for path,digest in proof['source_sha256'].items():
            if sha((ROOT/path).read_bytes())!=digest:raise ValueError('Changed baseline source: '+path)
    if old[0x5b9ab0:0x5b9ad0]!=b'\0\xbf'*16 or old[0x5b9a1e:0x5b9a22]!=bytes.fromhex('c5f80413'):
        raise ValueError('Wrong unused-space or hook preimage')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/menu_icons.S'),'-o','icons.o'],cwd=OUT)
    run(['arm-none-eabi-ld','--section-start=.iconhook=0x5b9a1e','--section-start=.icons=0x5b9ab0','-e','recipe_icons','icons.o','-o','icons.elf'],cwd=OUT)
    elf=ELF(OUT/'icons.elf');new=bytearray(old)
    size=next(s[5] for s in elf.sections if s[3]==0x5b9ab0)
    if size>32:raise ValueError('Icon helper too large')
    new[0x5b9ab0:0x5b9ab0+size]=elf.read(0x5b9ab0,size)
    new[0x5b9a1e:0x5b9a22]=elf.read(0x5b9a1e,4)
    (OUT/'viewUnified2.so').write_bytes(new)
    data=(usr/'share/app/image_cmn_43.uxc').read_bytes()
    if sha(data)!=ICON_SHA:raise ValueError('Wrong image UXC baseline')
    changed=patch(data)
    (OUT/'image_cmn_43.uxc').write_bytes(changed)
    # Regenerate original test fixtures from pinned local Sony inputs; old proofs
    # stay unchanged. Test the COMPLETE new code block, including old v3 hooks.
    baseline={n:(ROOT/'.lab'/n/'proof.json').read_bytes() for n in ('menu-lazy','menu-identity')}
    try:
        menu_lazy.build(usr)
        (ROOT/'.lab/menu-lazy/proof.json').write_bytes(baseline['menu-lazy'])
        menu_identity.build(usr)
    finally:
        for n,data in baseline.items():(ROOT/'.lab'/n/'proof.json').write_bytes(data)
    for kind,suite in [('lazy',menu_lazy),('identity',menu_identity)]:
        test=OUT/kind;test.mkdir(exist_ok=True)
        origin=ROOT/('.lab/menu-lazy' if kind=='lazy' else '.lab/menu-identity')
        for source in origin.iterdir():
            if source.suffix in ('.bin','.h') or source.name=='fixture.S':shutil.copy2(source,test/source.name)
        (test/'body.bin').write_bytes(new[0x5b98dc:0x5b9b6e])
        assembly=['.syntax unified','.thumb','.section .body,"ax"','.global persistent_dispatch','.thumb_func','persistent_dispatch:', '.incbin "body.bin"']
        addresses={'hook':(0x5b9fba,4),'viewhook':(0x5bb266,4)} if kind=='lazy' else {'remember':(0x5bb18e,4),'reopen':(0x5bb9de,4)}
        for name,(at,n) in addresses.items():
            (test/(name+'.bin')).write_bytes(new[at:at+n])
            assembly += [f'.section .{name},"ax"',f'.incbin "{name}.bin"']
            if kind=='lazy':assembly+=['bx lr' if name=='hook' else 'pop {r3,pc}']
        assembly+=['.section .note.GNU-stack,"",%progbits']
        (test/'body.S').write_text('\n'.join(assembly)+'\n')
        run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c','body.S','-o','body.o'],cwd=test)
        run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c','fixture.S','-o','fixture.o'],cwd=test)
        locations=['--section-start=.body=0x5b98dc']+[f'--section-start=.{name}={at:#x}' for name,(at,_) in addresses.items()]
        locations+= ['--section-start=.fixture=0xa60998','--section-start=.original_init=0x40bbec','--section-start=.get_id=0x15ed04','--section-start=.testtext=0x100000'] if kind=='lazy' else ['--section-start=.reverse=0x5b9b70','--section-start=.tables=0x7aa168','--section-start=.fnselect=0x197d78','--section-start=.fnmap=0x19a0fc','--section-start=.cursor=0x15e118','--section-start=.test=0x100000','--section-start=.remember_return=0x5bb192','--section-start=.reopen_return=0x5bb9e2']
        run(['arm-none-eabi-ld','-shared','-Bsymbolic','-z','noexecstack',*locations,'body.o','fixture.o','-o','fixture.so'],cwd=test)
    return {'previous_view_sha256':sha(old),'icon_sha256':ICON_SHA,'init_file_offset':0x5b9a1e,
            'scope':'RW icons only; no FL recipe or image-processing changes',
            'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in ('research/menu_icons.py','research/menu_icons.S','research/menu_icons_harness.c','research/style_icons.py','research/menu_lazy.py','research/menu_lazy_harness.c','research/menu_identity.py','research/menu_identity_harness.c')},
            'files':{n:sha((OUT/n).read_bytes()) for n in ('viewUnified2.so','image_cmn_43.uxc')}}

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('usr','kernel','busybox','sony-root'):cli.add_argument('--'+name,type=Path,required=True)
    a=cli.parse_args();proof=build(a.usr)
    # The established runners compile their harness path. Intercept only that
    # explicit path to add icon assertions, preserving the entire old suite.
    original_run=menu_lazy.run
    def with_icons(cmd,**kw):
        cmd=[str(ROOT/'research/menu_icons_harness.c') if x==str(ROOT/'research/menu_lazy_harness.c') else x for x in cmd]
        return original_run(cmd,**kw)
    menu_lazy.OUT=OUT/'lazy';menu_lazy.run=with_icons
    menu_lazy.test(a.kernel,a.busybox,a.sony_root)
    menu_identity.OUT=OUT/'identity';menu_identity.test(a.kernel,a.busybox,a.sony_root)
    proof['qemu_logs']={n:sha((OUT/n/'qemu.log').read_bytes()) for n in ('lazy','identity')}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
