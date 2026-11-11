#!/usr/bin/env python3
"""Local-only Thumb inspection with original ARM PLT dependency names."""
import argparse
from pathlib import Path
import subprocess
import capstone
from elf32 import ELF


def listing(path, start, count):
    e=ELF(path)
    thumb=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
    thumb.detail=True; thumb.skipdata=True
    arm=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_ARM);arm.detail=True
    cache={}
    def target(at):
        if at in cache:return cache[at]
        result=''
        try:
            ip=0
            for i in arm.disasm(e.read(at,12),at):
                if i.mnemonic=='add':
                    imm=i.operands[2].imm
                    if len(i.operands)==4:
                        n=i.operands[3].imm
                        imm=((imm>>n)|(imm<<(32-n)))&0xffffffff
                    ip=(i.address+8 if i.operands[1].reg==capstone.arm.ARM_REG_PC else ip)+imm
                elif i.mnemonic=='ldr':
                    n=e.relocations[ip+i.operands[1].mem.disp][1]['name']
                    result=subprocess.run(['arm-none-eabi-c++filt',n],text=True,capture_output=True,check=True).stdout.strip()
        except (KeyError,ValueError):pass
        cache[at]=result
        return result
    result=[]
    for i in thumb.disasm(e.read(start,count),start):
        extra=''
        if i.id and i.mnemonic in ('blx','b.w','bl') and i.operands[0].type==capstone.arm.ARM_OP_IMM:
            extra=target(i.operands[0].imm)
        if i.id and i.mnemonic.startswith('ldr') and len(i.operands)>1 and i.operands[1].type==capstone.arm.ARM_OP_MEM and i.operands[1].mem.base==capstone.arm.ARM_REG_PC:
            at=((i.address+4)&~3)+i.operands[1].mem.disp
            extra=f'{at:x}={e.word(at):x}'
        result.append(f'{i.address:08x}: {i.mnemonic:7s} {i.op_str:35s} ; {extra}')
    return '\n'.join(result)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('library',type=Path)
    p.add_argument('start',type=lambda x:int(x,16))
    p.add_argument('count',type=lambda x:int(x,16))
    a=p.parse_args();print(listing(a.library,a.start,a.count),end='')
