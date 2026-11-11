#!/usr/bin/env python3
"""Correct the separate native belt index and its orange image resource."""
import argparse
import importlib.util
import io
import json
import shutil
import struct
import subprocess
from pathlib import Path

from elf32 import ELF
from style_icons import Images, badge, decode, encode, swizzle
import menu_icons_display as display
import menu_lazy
import menu_identity

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/menu-icons-belt'
sha=menu_lazy.sha
run=menu_lazy.run

def fixed_stream(raw,size):
    # A short raw block plus compressed remainder keeps the entire original
    # record, including length, unchanged even in an old mapped header page.
    n=size-4-len(encode(raw));seen=set()
    for _ in range(32):
        if not 0<n<=4096 or n>=len(raw) or n in seen:break
        seen.add(n);tail=encode(raw[n:])
        if n+4+len(tail)==size:
            result=b'\x0f\0'+struct.pack('<H',n)+raw[:n]+tail
            if decode(result)!=raw:raise ValueError('Exact-length stream failed round trip')
            return result
        n=size-4-len(tail)
    raise ValueError('Cannot preserve original compressed length')

def build(usr,lz77_source):
    previous=ROOT/'.lab/creative-icons-display'
    manifest=json.loads((previous/'manifest.json').read_text())
    base_proof=ROOT/'.lab/menu-icons-display/proof.json'
    if sha(base_proof.read_bytes())!=manifest['native_proof_sha256']:raise ValueError('Previous proof changed')
    inherited=json.loads(base_proof.read_text())['source_sha256']
    for p,digest in inherited.items():
        if sha((ROOT/p).read_bytes())!=digest:raise ValueError('Changed previous source: '+p)
    old=(previous/'viewUnified2.so').read_bytes();icons=(previous/'image_cmn_43.uxc').read_bytes()
    for path,data in [('/lib/viewUnified2.so',old),('/share/app/image_cmn_43.uxc',icons)]:
        if sha(data)!=manifest['files'][path]['after_sha256']:raise ValueError('Wrong installed preimage')
    if old[0x5b9ac0:0x5b9ac4]!=bytes.fromhex('704700bf') or old[0x5b9b10:0x5b9b1a]!=b'\0\xbf'*5:
        raise ValueError('Wrong initializer tail or unused space')
    obj=ELF(usr/'lib/libObj.so')
    if sha(obj.data)!='1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23':
        raise ValueError('Wrong native menu getter library')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/menu_icons_belt.S'),'-o','patch.o'],cwd=OUT)
    run(['arm-none-eabi-ld','--section-start=.belthook=0x5b9ac0','--section-start=.belt=0x5b9b10',
         '-e','recipe_belt','patch.o','-o','patch.elf'],cwd=OUT)
    patch=ELF(OUT/'patch.elf');new=bytearray(old)
    for at,n in [(0x5b9ac0,4),(0x5b9b10,10)]:new[at:at+n]=patch.read(at,n)
    images=Images(icons);record,flags,w,h,begin,size=images.records[0x5c9b5]
    if (record,flags,w,h,begin,size)!=(60340,0xe0000000,70,35,11152140,1974):
        raise ValueError('Wrong orange slot-3 Neutral resource')
    raw=swizzle(w,h,badge('RW',w,h,True));blob=fixed_stream(raw,size)
    spec=importlib.util.spec_from_file_location('reference_lz77',lz77_source)
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    stream=io.BytesIO(blob);decoded=b''
    while stream.tell()<len(blob):decoded+=reference.inflateLz77(stream)
    if decoded!=raw:raise ValueError('Independent fwtool decoder disagrees')
    edited=bytearray(icons);edited[begin:begin+size]=blob
    if edited[:begin]!=icons[:begin] or edited[begin+size:]!=icons[begin+size:]:raise ValueError('Other resource bytes changed')
    if Images(edited).pixels(0x5c9b5)!=(w,h,badge('RW',w,h,True)):raise ValueError('Wrong orange pixels')
    (OUT/'viewUnified2.so').write_bytes(new);(OUT/'image_cmn_43.uxc').write_bytes(edited)
    # Reproduce all previous fixtures and retain the exact deployed proof.
    saved=base_proof.read_bytes();old_run=display.run;links={}
    def capture(cmd,**kw):
        if cmd[0]=='arm-none-eabi-ld' and '-shared' in cmd and 'body.o' in cmd:
            links[Path(kw['cwd']).name]=list(cmd)
        return run(cmd,**kw)
    display.run=capture
    try:display.build(usr)
    finally:display.run=old_run;base_proof.write_bytes(saved)
    for kind in ('lazy','identity'):
        directory=OUT/kind;directory.mkdir(exist_ok=True)
        for source in (display.OUT/kind).iterdir():
            if source.suffix in ('.bin','.h','.S'):shutil.copy2(source,directory/source.name)
        (directory/'body.bin').write_bytes(new[0x5b98dc:0x5b9b6e])
        link=links[kind]
        if kind=='lazy':
            suite=(ROOT/'research/menu_icons_display_harness.c').read_text()
            if suite.count('int main(void) {')!=1:raise ValueError('Previous harness structure changed')
            (directory/'display-suite.h').write_text(suite.replace('int main(void) {','static int display_suite(void) {'))
            additions=['.syntax unified']
            view=ELF(usr/'lib/viewUnified2.so')
            blobs={'beltordinary':(0x5b71e8,0x110,view,'native_belt_ordinary'),
                   'belthighlighted':(0x5b7bd0,0x188,view,'native_belt_highlighted'),
                   'beltgetter':(0x14f560,0x70,obj,'native_belt_getter'),
                   'belttable0':(0x7a6118,360*12,view,None),
                   'belttable1':(0x7a2174,360*12,view,None)}
            for name,(at,n,elf,symbol) in blobs.items():
                (directory/(name+'.bin')).write_bytes(elf.read(at,n))
                additions += [f'.section .{name},"'+('ax' if symbol else 'a')+'"']
                if symbol:additions+=['.thumb',f'.global {symbol}','.thumb_func',symbol+':']
                additions += [f'.incbin "{name}.bin"']
                link.insert(1,f'--section-start=.{name}={at:#x}')
            additions += ['.section .beltid,"ax"','.arm','ldr r0,[r1,#8]','bx lr',
                          '.section .beltvisible,"ax"','.thumb','bx lr']
            link[1:1]=['--section-start=.beltid=0x15ce70','--section-start=.beltvisible=0x5b7aba']
            with (directory/'fixture.S').open('a') as f:f.write('\n'+'\n'.join(additions)+'\n')
            expected=[]
            for table in (0x7a6118,0x7a2174):
                values=[]
                for i in range(13):
                    index=view.word(0xa60998+i*40+24)
                    values.append('{'+','.join(str(x) for x in struct.unpack('<II',view.read(table+12*index,8)))+'}')
                if struct.unpack('<II',view.read(table+359*12,8))!=(0x0205c76d,0x0205c9b5):raise ValueError('Wrong native RW table entry')
                expected.append('{'+','.join(values)+'}')
            (directory/'belt-expected.h').write_text(',\n'.join(expected))
        for name in ('body','fixture'):
            run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',name+'.S','-o',name+'.o'],cwd=directory)
        run(link,cwd=directory)
    source=dict(inherited)
    for name in ('menu_icons_belt.py','menu_icons_belt.S','menu_icons_belt_harness.c'):
        p='research/'+name;source[p]=sha((ROOT/p).read_bytes())
    return {'scope':'Belt icon index 320 to 359 only on custom row; orange RW pixels in existing fixed-length stream',
        'previous_view_sha256':sha(old),'icon_sha256':sha(icons),'init_file_offset':0x5b9ac0,
        'source_sha256':source,'libobj_sha256':sha(obj.data),'reference_lz77_sha256':sha(lz77_source.read_bytes()),
        'files':{n:sha((OUT/n).read_bytes()) for n in ('viewUnified2.so','image_cmn_43.uxc')}}

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('usr','kernel','busybox','sony-root','lz77-source'):cli.add_argument('--'+name,type=Path,required=True)
    a=cli.parse_args();proof=build(a.usr,a.lz77_source)
    original_run=menu_lazy.run
    def belt_harness(cmd,**kw):
        cmd=[str(ROOT/'research/menu_icons_belt_harness.c') if x==str(ROOT/'research/menu_lazy_harness.c') else x for x in cmd]
        if cmd[0]=='arm-none-eabi-gcc':cmd+=['-I',str(ROOT/'research')]
        try:return original_run(cmd,**kw)
        except subprocess.TimeoutExpired as error:
            (OUT/'lazy/qemu-failed.log').write_bytes((error.stdout or b'')+(error.stderr or b''))
            print((error.stdout or b'').decode(errors='replace'));raise
    menu_lazy.OUT=OUT/'lazy';menu_lazy.run=belt_harness
    menu_lazy.test(a.kernel,a.busybox,a.sony_root)
    if b'QEMU_RW_BELT_PASSED' not in (OUT/'lazy/qemu.log').read_bytes():raise ValueError('Belt tests missing')
    menu_identity.OUT=OUT/'identity';menu_identity.test(a.kernel,a.busybox,a.sony_root)
    proof['qemu_logs']={n:sha((OUT/n/'qemu.log').read_bytes()) for n in ('lazy','identity')}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
