#!/usr/bin/env python3
"""Test ARM SHA-256 against hashlib and pin the fixed-path read-only payload."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/image-hash'
def sha(data):return hashlib.sha256(data).hexdigest()
def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    sizes=(0,1,2,55,56,63,64,65,127,128,129,4095,4096,4097,8200)
    data=bytes((i*37+11)&255 for i in range(8200))
    header='static const unsigned sizes[]={'+','.join(map(str,sizes))+'};\n'
    header+='static const unsigned char expected[][32]={'+','.join('{'+','.join(map(str,hashlib.sha256(data[:n]).digest()))+'}' for n in sizes)+'};\n'
    (OUT/'vectors.h').write_text(header)
    (OUT/'guest.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }\n')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-Os','-ffreestanding','-fno-builtin','-nostdlib','-T','guest.ld','-I',str(OUT),'-I',str(ROOT/'payloads'),str(ROOT/'ui/start.S'),str(ROOT/'research/image_hash_harness.c'),'-lgcc','-o','hash.elf'],cwd=OUT)
    r=run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/hash.elf,cpu-num=0'],capture_output=True,timeout=20)
    (OUT/'qemu.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(),end='')
    if b'QEMU_IMAGE_SHA256_PASSED' not in r.stdout or b'FAIL ' in r.stdout:raise ValueError('SHA256 tests failed')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-c',str(ROOT/'payloads/a7-image-hash.c'),'-o','hash.o'],cwd=OUT)
    run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack','hash.o','-o','hash.so'],cwd=OUT)
    sources=('payloads/sha256.h','payloads/a7-image-hash.c','research/image_hash_test.py','research/image_hash_harness.c','ui/start.S')
    proof={'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in sources},'payload_sha256':sha((OUT/'hash.so').read_bytes()),'scope':'ARM hash arithmetic and streaming boundaries; direct file I/O validated separately on camera'}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':main()
