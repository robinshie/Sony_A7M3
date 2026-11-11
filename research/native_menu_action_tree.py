#!/usr/bin/env python3
"""Exercise original SettingMenu selectors and Save dispatch with real native nodes."""
import argparse, hashlib, json, struct, subprocess
from pathlib import Path
from elf32 import ELF
from native_adjust_fixture import SHA as CAUTION_SHA, PIECES, STUBS
from creative_dispatch import VIEW_SHA
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-menu-action-tree'
VIEW_PIECES=[(0x216a18,0x24,'process'),(0x216ea8,0x42,'main_select'),
             (0x217144,0x30,'category_select'),(0x217c7c,0xd6,'action')]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',type=Path,required=True);a=p.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
 view=ELF(a.usr/'lib/viewUnified2.so');caution=ELF(a.usr/'lib/CautionConfig.so')
 assert sha(view.data)==VIEW_SHA and sha(caution.data)==CAUTION_SHA
 asm='.syntax unified\n';sections=[];pieces=[]
 for elf,items in [(caution,PIECES),(view,VIEW_PIECES)]:
  for va,size,name in items:
   raw=elf.read(va,size);(OUT/f'{name}.bin').write_bytes(raw)
   asm+=f'.section .native_{name},"ax"\n.incbin "{name}.bin"\n';sections.append((va,f'.native_{name}'))
   pieces.append({'va':hex(va),'size':size,'sha256':sha(raw)})
 vt=bytearray(caution.read(0x918ec0,268))
 for offset in range(4,268,4):struct.pack_into('<I',vt,offset,caution.relocations[0x918ec0+offset][1]['value'])
 (OUT/'vtable.bin').write_bytes(vt)
 asm+='.section .native_vtable,"a"\n.incbin "vtable.bin"\n.section .native_got,"a"\n.word 0x918ec0\n'
 sections.extend([(0x918ec0,'.native_vtable'),(0x9880b0,'.native_got')])
 for va,(destination,thumb) in dict(STUBS,**{}).items():
  name=f'.stub_{va:x}';sections.append((va,name));asm+=f'.section {name},"ax"\n'
  if thumb:asm+=f'.thumb\nldr.w ip,[pc,#4]\nbx ip\nnop\n.word {destination}\n'
  else:asm+=f'.arm\nldr ip,[pc,#0]\nbx ip\n.word {destination}\n'
 asm+='.section .flag,"ax"\n.arm\nb model_flag\n.section .note.GNU-stack,"",%progbits\n';sections.append((0x15aae8,'.flag'))
 (OUT/'native.S').write_text(asm)
 ld='ENTRY(_start)\nSECTIONS {\n. = 0x100000;\n.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
 ld+=''.join(f'{n} {va:#x} : {{ *({n}) }}\n' for va,n in sorted(sections))+'}\n';(OUT/'test.ld').write_text(ld)
 sources=['research/native_menu_action_tree.py','research/native_menu_action_tree.c','research/native_menu.c','research/native_menu.h','research/native_adjust.c','research/native_adjust.h','research/native_adjust_fixture.py','ui/start.S']
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-nostdlib','-T','test.ld',str(ROOT/'ui/start.S'),str(ROOT/'research/native_adjust.c'),str(ROOT/'research/native_menu.c'),str(ROOT/'research/native_menu_action_tree.c'),'native.S','-lgcc','-o','action-tree.elf'],cwd=OUT,check=True)
 r=subprocess.run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/action-tree.elf,cpu-num=0'],capture_output=True,timeout=20,check=True)
 log=r.stdout+r.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
 assert b'NATIVE_MENU_ACTION_TREE_PASSED' in log and b'FAIL ' not in log
 (OUT/'proof.json').write_text(json.dumps({'view_sha256':VIEW_SHA,'caution_sha256':CAUTION_SHA,'pieces':pieces,'source_sha256':{s:sha((ROOT/s).read_bytes()) for s in sources},'qemu_log_sha256':sha(log),'scope':'Original SettingMenu main/submenu selected-row accessors, property extraction and exec action with original Caution nodes. Corrected real page graph dispatches Save; old flat graph cannot. Backend and stock model flag are modeled. No physical button or renderer execution.','camera_execution':False},indent=2)+'\n')
if __name__=='__main__':main()
