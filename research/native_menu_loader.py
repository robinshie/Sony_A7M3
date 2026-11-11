#!/usr/bin/env python3
"""Build and test a bounded MENU loader over the verified RW firmware image."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from elf32 import ELF
from creative_dispatch import VIEW_SHA

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-menu-loader'
RW_SHA='946cc404800c39e20a46099aa1f381cee4fe2b0e308946d5f572a5305b941f75'
HOOK=0x20d068
SITES={'menu_hook':(HOOK,4),'menu_loader_a':(0x5b9a7c,52),'menu_loader_b':(0x5b9b1c,82)}
def sha(b):return hashlib.sha256(b).hexdigest()
def run(args,**kw):return subprocess.run(args,check=True,**kw)

def main():
 cli=argparse.ArgumentParser(description=__doc__)
 cli.add_argument('--usr',type=Path,required=True)
 cli.add_argument('--rw-view',type=Path,default=ROOT/'.lab/creative-icons-belt/viewUnified2.so')
 a=cli.parse_args();OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
 original=ELF(a.usr/'lib/viewUnified2.so');before=a.rw_view.read_bytes()
 if sha(original.data)!=VIEW_SHA or sha(before)!=RW_SHA:raise ValueError('Original/RW firmware pin mismatch')
 if before[HOOK:HOOK+4]!=original.read(HOOK,4):raise ValueError('Original factory hook changed')
 for name,(at,capacity) in SITES.items():
  if name!='menu_hook' and before[at:at+capacity]!=b'\0\xbf'*(capacity//2):raise ValueError('Reserved RW cave mismatch')
 run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-c',str(ROOT/'research/native_menu_loader.S'),'-o','loader.o'],cwd=OUT)
 run(['arm-none-eabi-ld',*[f'--section-start=.{n}={at:#x}' for n,(at,_) in SITES.items()],'-e','native_menu_loader','loader.o','-o','loader.elf'],cwd=OUT)
 patch=ELF(OUT/'loader.elf');edited=bytearray(before);metadata={}
 for name,(at,capacity) in SITES.items():
  section=next(s for s in patch.sections if s[3]==at)
  size=section[5]
  if size>capacity:raise ValueError('Loader exceeds reserved NOP cave')
  data=patch.read(at,size);edited[at:at+size]=data;(OUT/(name+'.bin')).write_bytes(data)
  metadata[name]={'va':at,'size':size,'capacity':capacity,'before_hex':before[at:at+size].hex(),'after_hex':data.hex()}
 # Complete bytewise exclusion proof: no old RW menu/icon bytes may change.
 allowed={i for n,m in metadata.items() for i in range(m['va'],m['va']+m['size'])}
 if any(i not in allowed for i,(x,y) in enumerate(zip(before,edited)) if x!=y):raise ValueError('Out-of-scope firmware change')
 (OUT/'viewUnified2.so').write_bytes(edited)
 factory=bytearray(original.read(0x20d056,0x24));factory[HOOK-0x20d056:HOOK-0x20d056+4]=patch.read(HOOK,4)
 (OUT/'factory.bin').write_bytes(factory)
 (OUT/'dlopen_plt.bin').write_bytes(original.read(0x15d958,12))
 (OUT/'dlsym_plt.bin').write_bytes(original.read(0x15c8dc,12))
 (OUT/'native.S').write_text('''.syntax unified
.section .factory,"ax"
.thumb
.global stock_factory
.thumb_func
stock_factory: .incbin "factory.bin"
.section .loader_a,"ax"
.incbin "menu_loader_a.bin"
.section .loader_b,"ax"
.incbin "menu_loader_b.bin"
.section .allocate,"ax"
.arm
b mock_alloc
.section .constructor,"ax"
.thumb
b.w mock_ctor
.section .dlopen_plt,"ax"
.arm
.incbin "dlopen_plt.bin"
.section .dlsym_plt,"ax"
.arm
.incbin "dlsym_plt.bin"
.section .dlopen_got,"aw"
.global dlopen_slot
dlopen_slot: .word 0
.section .dlsym_got,"aw"
.global dlsym_slot
dlsym_slot: .word 0
.section .note.GNU-stack,"",%progbits
''')
 (OUT/'start.S').write_text('''.syntax unified
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
 ld='ENTRY(_start)\nSECTIONS {\n. = 0x40200000;\n.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
 loc={'factory':0x20d056,'loader_a':SITES['menu_loader_a'][0],'loader_b':SITES['menu_loader_b'][0],
      'allocate':0x15867c,'constructor':0x20cda0,'dlopen_got':0x8e54dc,'dlsym_got':0x8e4ff4,
      'dlopen_plt':0x15d958,'dlsym_plt':0x15c8dc}
 ld+=''.join(f'.{n} {at+0x40000000:#x} : {{ *(.{n}) }}\n' for n,at in sorted(loc.items(),key=lambda x:x[1]))+'}\n';(OUT/'guest.ld').write_text(ld)
 run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror',
      '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
      '-nostdlib','-T','guest.ld','start.S','native.S',str(ROOT/'research/native_menu_loader_harness.c'),'-lgcc','-o','loader-test.elf'],cwd=OUT)
 r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-smp','1','-m','1024','-nodefaults','-audio','none','-nic','none',
        '-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native',
        '-device',f'loader,file={OUT}/loader-test.elf,cpu-num=0'],capture_output=True,timeout=30)
 log=r.stdout+r.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
 if b'NATIVE_MENU_LOADER_PASSED' not in r.stdout or b'FAIL ' in log:raise ValueError('Loader test failed')
 sources=['research/native_menu_loader'+s for s in ('.S','.py','_harness.c')]
 proof={'before_sha256':RW_SHA,'after_sha256':sha(edited),'patches':metadata,
        'source_sha256':{s:sha((ROOT/s).read_bytes()) for s in sources},'qemu_log_sha256':sha(log),
        'scope':'Original native MENU factory with new bounded loader; dynamic loader and module install mocked; no sensor or LCD emulation',
        'module_path':'/usr/lib/a7fl.so','entry':'int a7_fl_install(uintptr_t view_base, void *view_manager)',
        'constructor_original_va':0x20cda1,'native_display_rendered':False,'camera_integration':False,'flash_ready':False}
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':main()
