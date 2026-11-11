#!/usr/bin/env python3
"""Offline ARM test of single-parameter native adapter, with recorded boundaries."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parents[1];O=R/'.lab/sharpness-request'
def main():
 O.mkdir(parents=True,exist_ok=True)
 stubs={0x15867c:('allocate',False),0x1617cc:('parameter',True),0x15d230:('list',False),
        0x15c7b8:('add',False),0x15aa58:('request',False),0x159c64:('release',False)}
 asm='.syntax unified\n';ld='ENTRY(_start)\nSECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
 for at,(name,thumb) in stubs.items():
  asm+=f'.section .stub_{name},"ax"\n'+('.thumb\n' if thumb else '.arm\n')+f'ldr ip,1f\nbx ip\n.balign 4\n1: .word {name}\n'
  ld+=f'.stub_{name} {0x01000000+at:#x} : {{ *(.stub_{name}) }}\n'
 asm+='.section .note.GNU-stack,"",%progbits\n';(O/'stubs.S').write_text(asm);(O/'test.ld').write_text(ld+'}\n')
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-Os','-ffreestanding','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror','-I',str(R/'payloads'),'-T',str(O/'test.ld'),str(R/'ui/start.S'),str(O/'stubs.S'),str(R/'payloads/a7-fl-sharpness-native.c'),str(R/'research/sharpness_request_test.c'),'-lgcc','-o',str(O/'test.elf')],check=True)
 t=subprocess.run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/test.elf,cpu-num=0'],capture_output=True,timeout=15,check=True)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='')
 assert b'SHARPNESS_REQUEST_PASSED' in log and b'FAIL' not in log
 sources=['payloads/a7-fl-sharpness-native.c','payloads/a7-fl-sharpness-native.h','research/sharpness_request_test.c','research/sharpness_request_test.py','ui/start.S']
 sha=lambda b:hashlib.sha256(b).hexdigest()
 (O/'proof.json').write_text(json.dumps(dict(source_sha256={p:sha((R/p).read_bytes()) for p in sources},qemu_log_sha256=sha(log),camera_applied=False,scope='Adapter only; model/allocator boundaries mocked'),indent=2)+'\n')
if __name__=='__main__':main()
