#!/usr/bin/env python3
"""Generate private platform byte pins; compile bootstrap without USB access."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from elf32 import ELF

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-bootstrap'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usr',type=Path,required=True)
    args=parser.parse_args()
    backup=ELF(args.usr/'lib/libbackup.so');caution=ELF(args.usr/'lib/CautionConfig.so')
    expected='b6420f8f7cacade524e1ba7c5b0d8b06691c22ed793dca084fdf1c1d9ae092f3'
    if hashlib.sha256(backup.data).hexdigest()!=expected:raise ValueError('Backup library identity')
    from native_adjust_fixture import SHA
    if hashlib.sha256(caution.data).hexdigest()!=SHA:raise ValueError('Caution library identity')
    OUT.mkdir(parents=True,exist_ok=True)
    lines=[]
    for elf,name,offset in ((backup,'size',0x1174),(backup,'attr',0x11d4),(backup,'read',0x1204),
                            (backup,'write',0x1358),(caution,'ctor',0x68338c),(caution,'init',0x6830aa)):
        if any(offset<=p<offset+16 for p in elf.relocations):raise ValueError('Pin crosses relocation')
        lines.append('static const unsigned char a7_pin_'+name+'[16]={'+','.join(str(x) for x in elf.read(offset,16))+'};')
    (OUT/'a7-fl-bootstrap-pins.h').write_text('\n'.join(lines)+'\n')
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access',
                    '-Os','-Wall','-Wextra','-Werror','-fPIC','-ffreestanding','-fno-builtin',
                    '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-strict-aliasing',
                    '-I',str(ROOT/'payloads'),'-I',str(ROOT/'research'),'-I',str(OUT),'-c',
                    str(ROOT/'payloads/a7-fl-bootstrap.c'),'-o',str(OUT/'bootstrap.o')],check=True)
    sources=['payloads/a7-fl-bootstrap.c','payloads/a7-fl-bootstrap.h','research/native_bootstrap.py']
    (OUT/'compile-proof.json').write_text(json.dumps({
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        'pins_sha256':hashlib.sha256((OUT/'a7-fl-bootstrap-pins.h').read_bytes()).hexdigest(),
        'arm_compile_verified':True,'native_execution_tested':False,'early_boot_hook':'StillView UserEntry; live readiness unverified',
        'camera_integration':False,'flash_ready':False,
    },indent=2)+'\n')
    print('NATIVE_BOOTSTRAP_COMPILED; execution/lifecycle verification still required')


if __name__=='__main__':main()
