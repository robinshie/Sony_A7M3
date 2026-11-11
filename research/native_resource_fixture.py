#!/usr/bin/env python3
"""Verify expanded locale UXC files using original Sony ARM parser machine code.

Tests the real v7 header validator, packed index/record lookup and record ID/type
helpers. File mapping, ResourceManager cache lifecycle, fonts and LCD rendering
are outside this fixture. No camera or USB access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from elf32 import ELF

ROOT=Path(__file__).resolve().parents[1]
OBJ_SHA='1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23'
PIECES=[(0x81598c,0x13a,'index'),(0x816118,0x5c,'header'),
        (0x8207c6,0xc,'record_id'),(0x5f4450,0xe,'record_type')]


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usr',required=True,type=Path)
    p.add_argument('--before',type=Path,default=ROOT/'.lab/creative-icons-belt')
    p.add_argument('--after',type=Path,default=ROOT/'.lab/native-fl-strings')
    args=p.parse_args()
    elf=ELF(args.usr/'lib/libObj.so')
    if sha(elf.data)!=OBJ_SHA:p.error('Unexpected libObj.so SHA-256')
    proof=json.loads((args.after/'proof.json').read_text())
    for name,digest in proof['source_sha256'].items():
        if sha((ROOT/name).read_bytes())!=digest:p.error('Locale source changed after proof: '+name)
    expected=[('root','创意外观','Creative Look'),('fl','FL（实验版）','FL Experimental'),
              ('contrast','对比度','Contrast'),('highlights','高光','Highlights'),
              ('shadows','阴影','Shadows'),('fade','褪色','Fade'),('saturation','饱和度','Saturation'),
              ('sharpness','锐度','Sharpness'),('range','锐度范围','Sharpness Range'),('clarity','清晰度','Clarity')]
    if proof['resources']!={name:0x0204fd9e+i for i,(name,_,_) in enumerate(expected)}:
        p.error('Unexpected resource assignment')
    out=ROOT/'.lab/native-resource';out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)
    asm='.syntax unified\n';sections=[];parts=[]
    for va,size,name in PIECES:
        data=elf.read(va,size);(out/f'{name}.bin').write_bytes(data)
        asm+=f'.section .native_{name},"ax"\n.incbin "{name}.bin"\n';sections.append((va,f'.native_{name}'))
        parts.append({'va':hex(va),'bytes':size,'sha256':sha(data)})
    asm+='.section .native_log,"ax"\n.arm\nldr ip, [pc, #0]\nbx ip\n.word unexpected_log\n'
    sections.append((0x1077a8,'.native_log'))
    metadata=[];header='#include <stdint.h>\n'
    for column,language in enumerate(('simplifiedchinese','english')):
        name=f'string_{language}.uxc';sizes=[]
        for state,folder in [('before',args.before),('after',args.after)]:
            data=(folder/name).read_bytes()
            if sha(data)!=proof['files'][name][state+'_sha256']:p.error('Locale proof hash mismatch: '+name+'/'+state)
            output=f'{state}_{language}.bin';(out/output).write_bytes(data);sizes.append(len(data))
            symbol=f'resource_{state}_{column}'
            asm+=f'.section .resource_data,"a"\n.balign 4\n.global {symbol}\n{symbol}:\n.incbin "{output}"\n'
            header+=f'extern unsigned char {symbol}[];\n'
        metadata.append({'file':name,'before_sha256':proof['files'][name]['before_sha256'],'after_sha256':proof['files'][name]['after_sha256'],'before_bytes':sizes[0],'after_bytes':sizes[1]})
        header+=f'static const unsigned resource_sizes_{column}[2]={{{sizes[0]},{sizes[1]}}};\n'
        header+=f'static const char *resource_labels_{column}[10]={{\n'
        for row in expected:
            # Unambiguous UTF-8 octets; no execution or shell interpolation.
            header+='"'+''.join('\\%03o'%b for b in row[column+1].encode('utf-8'))+'",\n'
        header+='};\n'
    (out/'resource_data.h').write_text(header)
    (out/'native.S').write_text(asm)
    ld='ENTRY(_start)\nSECTIONS {\n. = 0x100000;\n.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n. = ALIGN(4096);\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    ld+=''.join(f'{name} {va:#x} : {{ *({name}) }}\n' for va,name in sorted(sections))
    ld+='.resource_data 0x02000000 : { *(.resource_data) }\n}\n'
    (out/'guest.ld').write_text(ld)
    gcc,qemu=shutil.which('arm-none-eabi-gcc'),shutil.which('qemu-system-arm')
    if not gcc or not qemu:p.error('ARM GCC and QEMU required')
    subprocess.run([gcc,'-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-nostdlib','-I',str(out),'-T','guest.ld',str(ROOT/'ui/start.S'),str(ROOT/'research/native_resource_harness.c'),'native.S','-lgcc','-o','resource.elf'],cwd=out,check=True)
    run=subprocess.run([qemu,'-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/resource.elf,cpu-num=0'],capture_output=True,text=True,timeout=20,check=True)
    (out/'resource.log').write_text(run.stdout+run.stderr);print(run.stdout,end='')
    if 'NATIVE_RESOURCE_TESTS_PASSED' not in run.stdout or 'FAIL' in run.stdout:raise ValueError('Native UXC parser rejected expanded resource')
    report={'libobj_sha256':OBJ_SHA,'native_components':parts,'locales':metadata,
            'input_proof_sha256':sha((args.after/'proof.json').read_bytes()),
            'source_sha256':{n:sha((ROOT/'research'/n).read_bytes()) for n in ('native_resource_fixture.py','native_resource_harness.c')},
            'scope':'Original Sony v7 header validation, count/index/data-base extraction, mixed short/long record lookup and record ID/type; all prior entries compared, every new UTF-8 label exact. No OS file loader/cache/font/LCD/camera validation.',
            'flash_ready':False,'log':run.stdout.splitlines()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
