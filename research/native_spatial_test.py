#!/usr/bin/env python3
"""Test the experimental spatial reference on host + ARM. No camera access."""
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/spatial-reference'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=['payloads/a7-fl-spatial.c','payloads/a7-fl-spatial.h','research/native_spatial_harness.c','research/native_spatial_test.py','ui/start.S']
    common=['-O2','-Wall','-Wextra','-Werror','-I',str(ROOT/'payloads'),str(ROOT/sources[0]),str(ROOT/sources[2])]
    run(['clang',*common,'-fsanitize=address,undefined','-o',str(OUT/'host-test')])
    host=run([str(OUT/'host-test')],capture_output=True,timeout=30)
    (OUT/'host.log').write_bytes(host.stdout+host.stderr)
    (OUT/'guest.ld').write_text('''ENTRY(_start)
SECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) }
.rodata : { *(.rodata*) } .data : { *(.data*) }
.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }
''')
    run(['arm-none-eabi-gcc',*common,'-mcpu=cortex-a9','-mthumb','-mno-unaligned-access',
         '-DA7_SPATIAL_QEMU','-ffreestanding','-fno-builtin','-nostdlib','-T',str(OUT/'guest.ld'),
         str(ROOT/'ui/start.S'),'-lgcc','-o',str(OUT/'spatial.elf')])
    arm=run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults',
             '-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio',
             '-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/spatial.elf,cpu-num=0'],
             capture_output=True,timeout=45)
    (OUT/'qemu.log').write_bytes(arm.stdout+arm.stderr)
    for result in (host,arm):
        print(result.stdout.decode(),end='')
        if b'SPATIAL_REFERENCE_PASSED' not in result.stdout or b'FAIL' in result.stdout+result.stderr:raise ValueError('Spatial test failed')
    if host.stdout!=arm.stdout:raise ValueError('Host and ARM results differ')
    digest=lambda b:hashlib.sha256(b).hexdigest()
    proof=dict(source_sha256={p:digest((ROOT/p).read_bytes()) for p in sources},
        host_log_sha256=digest(host.stdout+host.stderr),qemu_log_sha256=digest(arm.stdout+arm.stderr),
        log=arm.stdout.decode().splitlines(),workspace_bytes_at_6000_pixels=420000,
        inplace_workspace_bytes_at_6000_pixels=576000,
        camera_hook=False,hardware_isp_tested=False,camera_image_tested=False,flash_ready=False,
        scope='Own experimental 8-bit luma spatial kernel; independent 2-D oracle, ASan/UBSan host, same C under ARM QEMU')
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
