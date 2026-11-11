#!/usr/bin/env python3
"""Run the original native action handler; this does not assert physical key mapping."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from elf32 import ELF
from creative_dispatch import VIEW_SHA
R=Path(__file__).resolve().parents[1];O=R/'.lab/native-menu-action'
def run(a,**kw):return subprocess.run(a,check=True,**kw)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--usr',type=Path,required=True);a=p.parse_args();O.mkdir(parents=True,exist_ok=True)
 e=ELF(a.usr/'lib/viewUnified2.so');assert sha(e.data)==VIEW_SHA
 (O/'action.bin').write_bytes(e.read(0x217c7c,0xd6))
 asm='.syntax unified\n.thumb\n.section .original,"ax"\n.global original_action\n.thumb_func\noriginal_action: .incbin "action.bin"\n'
 for n,target in [('select_menu','mock_select'),('select_category','mock_select'),('process','mock_process')]:asm+=f'.section .{n},"ax"\nb.w {target}\n'
 asm+='.arm\n.section .flag,"ax"\nb mock_flag\n.section .note.GNU-stack,"",%progbits\n';(O/'native.S').write_text(asm)
 (O/'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
 cpsid if
 ldr sp,=0x41000000
 ldr r0,=__bss_start
 ldr r1,=__bss_end
 mov r2,#0
1: cmp r0,r1
 strlo r2,[r0],#4
 blo 1b
 bl guest_main
2: wfi
 b 2b
.section .note.GNU-stack,"",%progbits
''')
 (O/'test.ld').write_text('''ENTRY(_start)
SECTIONS {
 . = 0x40400000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) }
 .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }
 .flag 0x4015aae8 : { *(.flag) }
 .process 0x40216a18 : { *(.process) }
 .select_menu 0x40216ea8 : { *(.select_menu) }
 .select_category 0x40217144 : { *(.select_category) }
 .original 0x40217c7c : { *(.original) }
}
''')
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(R/'research')]
 run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','test.ld','start.S','native.S',str(R/'research/native_menu.c'),str(R/'research/native_menu_action_harness.c'),'-lgcc','-o','action-test.elf'],cwd=O)
 t=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/action-test.elf,cpu-num=0'],capture_output=True,timeout=15)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='');assert b'NATIVE_MENU_ACTION_PASSED' in log and b'FAIL ' not in log
 sources=['research/native_menu.h','research/native_menu.c','research/native_menu_action.py','research/native_menu_action_harness.c']
 (O/'proof.json').write_text(json.dumps({'view_sha256':VIEW_SHA,'original_range':[0x217c7c,0xd6],'source_sha256':{s:sha((R/s).read_bytes()) for s in sources},'qemu_log_sha256':sha(log),'scope':'Original ViewSettingMenu exec action handler with modeled selected-node accessor and native process-manager adapter. Physical key-to-action event mapping remains unverified.','camera_execution':False},indent=2)+'\n')
if __name__=='__main__':main()
