#!/usr/bin/env python3
"""Execute actual bootstrap guards in QEMU using mocked Linux/backend/module APIs."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-bootstrap-test'

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    loader=json.loads((ROOT/'.lab/native-menu-boot-loader/proof.json').read_text())
    if loader['module_call_lr_va']!=0x5b9b31 or loader['module_call_return_va']!=0x5b9b30:
        raise ValueError('Bootstrap fixture caller ABI differs from actual loader proof')
    for p,d in loader['source_sha256'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=d:raise ValueError('Loader source changed')
    (OUT/'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
 cpsid if
 ldr sp,=0x7ff00000
 ldr r0,=__bss_start
 ldr r1,=__bss_end
 mov r2,#0
1: cmp r0,r1
 strlo r2,[r0],#4
 blo 1b
 bl guest_main
2: wfi
 b 2b
.global test_call_install
test_call_install:
 push {r4,lr}
 ldr r4,=0x405b9b31
 mov lr,r4
 ldr r4,=a7_fl_install
 bx r4
.global test_old_call_install
test_old_call_install:
 push {r4,lr}
 ldr r4,=0x405b9b2f
 mov lr,r4
 ldr r4,=a7_fl_install
 bx r4
.section .old_return,"ax"
.thumb
pop {r4,pc}
.section .actual_return,"ax"
.thumb
pop {r4,pc}
.section .note.GNU-stack,"",%progbits
''')
    (OUT/'guest.ld').write_text('''ENTRY(_start)
SECTIONS {
 . = 0x70000000;
 .text : { *(.text.start) *(.text*) }
 .rodata : { *(.rodata*) }
 .data : { *(.data*) }
 .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }
 .old_return 0x405b9b2e : { *(.old_return) }
 .actual_return 0x405b9b30 : { *(.actual_return) }
}
''')
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-strict-aliasing','-I',str(ROOT/'payloads'),'-I',str(ROOT/'research'),'-I',str(ROOT/'.lab/native-bootstrap'),'-nostdlib','-T','guest.ld','start.S',str(ROOT/'research/native_bootstrap_test_harness.c'),'-lgcc','-o','bootstrap-test.elf'],cwd=OUT,check=True)
    run=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-smp','1','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/bootstrap-test.elf,cpu-num=0'],check=True,capture_output=True,timeout=30)
    log=run.stdout+run.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if b'NATIVE_BOOTSTRAP_TESTS_PASSED' not in log or b'FAIL ' in log:raise ValueError('Bootstrap guard fixture failed')
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources=['research/native_bootstrap_test.py','research/native_bootstrap_test_harness.c','payloads/a7-fl-bootstrap.c','payloads/a7-fl-bootstrap.h','payloads/a7-fl-module.h','payloads/a7-fl-runtime.h','payloads/a7-fl-posix.h','research/native_menu.h']
    proof={'source_sha256':{p:h(ROOT/p) for p in sources},'pins_sha256':h(ROOT/'.lab/native-bootstrap/a7-fl-bootstrap-pins.h'),
           'loader_proof_sha256':h(ROOT/'.lab/native-menu-boot-loader/proof.json'),'log_sha256':h(OUT/'qemu.log'),
           'scope':'Actual ARM bootstrap maps, byte pins, exact build/model and native page guards, with genuine call-site LR; syscalls, Backup API and resident module are recording mocks. No USB/camera execution.',
           'camera_integration':False,'flash_ready':False,'log':log.decode().splitlines()}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':main()
