#!/usr/bin/env python3
"""Guarded native Creative Style replay; offline ABI test, not an ISP test."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from elf32 import ELF
from creative_dispatch import VIEW_SHA

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-preview-request'
OFFSETS=(0x15867c,0x1617cc,0x15d230,0x15c7b8,0x15aa58,0x159c64)
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usr',required=True,type=Path);args=parser.parse_args()
    view=ELF(args.usr/'lib/viewUnified2.so')
    if sha(view.data)!=VIEW_SHA:raise ValueError('Requires pinned original view library')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    subprocess.run(['python3',str(ROOT/'research/creative_setter.py'),'--usr',str(args.usr)],check=True)
    pins='static const unsigned a7_preview_offsets[]={'+','.join(map(str,OFFSETS))+'};\n'
    pins+='static const unsigned char a7_preview_pins[6][16]={'+','.join('{'+','.join(map(str,view.read(p,16)))+'}' for p in OFFSETS)+'};\n'
    (OUT/'a7-fl-preview-pins.h').write_text(pins)
    ld='ENTRY(_start)\nSECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }}\n'
    (OUT/'test.ld').write_text(ld)
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-I',str(ROOT/'payloads'),'-I',str(OUT)]
    subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T',str(OUT/'test.ld'),str(ROOT/'ui/start.S'),str(ROOT/'research/native_preview_test.c'),'-lgcc','-o',str(OUT/'test.elf')],check=True)
    run=subprocess.run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/test.elf,cpu-num=0'],check=True,capture_output=True,timeout=30)
    log=run.stdout+run.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if b'NATIVE_PREVIEW_REQUEST_PASSED' not in log or b'FAIL' in log:raise ValueError('Preview request tests failed')
    sources=['payloads/a7-fl-preview.c','payloads/a7-fl-preview.h','payloads/a7-fl-runtime.h','research/native_preview_test.c','research/native_preview_test.py','research/creative_setter.py','research/creative_setter_harness.c','research/elf32.py','research/creative_dispatch.py','ui/start.S']
    proof=dict(source_sha256={p:sha((ROOT/p).read_bytes()) for p in sources},original_view_sha256=VIEW_SHA,pins_sha256=sha(pins.encode()),qemu_log_sha256=sha(log),artifact_sha256=sha((OUT/'test.elf').read_bytes()),original_setter_report_sha256=sha((ROOT/'.lab/creative-setter/report.json').read_bytes()),scope='Production replay guards; pinned native addresses, allocator and async model recorded; no preference writes',camera_applied=False,isp_refresh_verified=False)
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
