#!/usr/bin/env python3
"""Execute the r9 adapter and original native timer dispatcher in ARM QEMU."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from elf32 import ELF
from creative_dispatch import VIEW_SHA
from native_save_dialog import PINNED
R=Path(__file__).resolve().parents[1];O=R/'.lab/native-preview-cycle'
VIEW=(0x15867c,0x1617cc,0x15d230,0x15c7b8,0x159924,0x159c64,0x15d958,0x15c8dc,0x15bf38)
OBJ=(0x8641b2,0x86420c,0x861c3c)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',required=True,type=Path);a=p.parse_args()
 view=ELF(a.usr/'lib/viewUnified2.so');obj=ELF(a.usr/'lib/libObj.so')
 assert sha(view.data)==VIEW_SHA and sha(obj.data)==PINNED[0]
 O.mkdir(parents=True,exist_ok=True);(O/'proof.json').unlink(missing_ok=True)
 header=''
 for name,e,offsets in [('view',view,VIEW),('obj',obj,OBJ)]:
  header+=f'static const unsigned a7_cycle_{name}_offsets[]={{'+','.join(map(str,offsets))+'};\n'
  header+=f'static const unsigned char a7_cycle_{name}_pins[{len(offsets)}][16]={{'+','.join('{'+','.join(map(str,e.read(x,16)))+'}' for x in offsets)+'};\n'
 (O/'a7-fl-preview-cycle-pins.h').write_text(header)
 parts={0x861c3c:(0x6e,'dispatch'),0x86198e:(0x2e,'compare')}
 asm='.syntax unified\n';sections=[]
 for at,(n,name) in parts.items():
  (O/(name+'.bin')).write_bytes(obj.read(at,n));asm+=f'.section .{name},"ax"\n.incbin "{name}.bin"\n';sections.append((0x02000000+at,name))
 for at,name,thumb in [(0x100fd4,'clock_now',False),(0x10251c,'add_ms',False),(0x861858,'next_record',True),(0x8617d6,'detach_record',True)]:
  asm+=f'.section .{name},"ax"\n'+(('.thumb\n'+('nop\n' if at&2 else '')+f'ldr.w ip,[pc,#4]\nbx ip\nnop\n.word fixture_{name}\n') if thumb else f'.arm\nldr ip,[pc]\nbx ip\n.word fixture_{name}\n');sections.append((0x02000000+at,name))
 asm+='.section .note.GNU-stack,"",%progbits\n';(O/'native.S').write_text(asm)
 ld='ENTRY(_start)\nSECTIONS {\n'+''.join(f'.{n} {v:#x} : {{ *(.{n}) }}\n' for v,n in sorted(sections))+'. = 0x100000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }}\n';(O/'test.ld').write_text(ld)
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-I',str(R/'payloads'),'-I',str(O)]
 subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','test.ld',str(R/'ui/start.S'),'native.S',str(R/'research/native_preview_cycle_test.c'),'-lgcc','-o','test.elf'],cwd=O,check=True)
 t=subprocess.run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/test.elf,cpu-num=0'],check=True,capture_output=True,timeout=30)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='')
 assert b'NATIVE_PREVIEW_CYCLE_PASSED' in log and b'FAIL' not in log
 files=['payloads/a7-fl-preview-cycle.c','payloads/a7-fl-preview-cycle.h','payloads/a7-fl-preview.h','payloads/a7-fl-runtime.h','research/native_preview_cycle_test.py','research/native_preview_cycle_test.c','research/elf32.py','research/native_save_dialog.py','research/creative_dispatch.py','ui/start.S']
 proof=dict(source_sha256={n:sha((R/n).read_bytes()) for n in files},original_view_sha256=VIEW_SHA,original_obj_sha256=PINNED[0],native_ranges={n:dict(offset=hex(at),size=size,sha256=sha(obj.read(at,size))) for at,(size,n) in parts.items()},pins_sha256=sha(header.encode()),qemu_log_sha256=sha(log),module_timer_abi_tested=True,camera_execution=False,isp_refresh_verified=False,scope=__doc__+' Framework queue, allocation and backup access are modeled; no ISP or physical frame timing.')
 (O/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
