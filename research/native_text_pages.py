#!/usr/bin/env python3
"""Build/decode fixed text-page snapshots. This utility has no USB transport."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from elf32 import ELF
from creative_dispatch import VIEW_SHA
R=Path(__file__).resolve().parents[1];O=R/'.lab/native-text-pages';OFFSETS=(0x214000,0x20d000,0x5b9000)
def sha(b):return hashlib.sha256(b).hexdigest()
def run(a,**kw):return subprocess.run(a,check=True,**kw)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',type=Path);p.add_argument('--decode',type=Path)
 p.add_argument('--compare',type=Path,default=R/'.lab/native-menu-boot-loader/viewUnified2.so');a=p.parse_args()
 if a.decode:
  b=a.decode.read_bytes();assert len(b)==12388
  h=struct.unpack_from('<IIi4I',b);assert h[:2]==(0x41375450,1)
  expected=ELF(a.compare);pages=[]
  for i,offset in enumerate(OFFSETS):
   info=struct.unpack_from('<6I',b,28+i*24);actual=b[100+i*4096:100+(i+1)*4096];before=expected.read(offset,4096)
   differences=[j for j,(x,y) in enumerate(zip(actual,before)) if x!=y]
   path=a.decode.with_suffix(f'.{offset:06x}.bin');path.write_bytes(actual)
   pages.append({'offset':offset,'address':info[1],'map_low':info[2],'map_high':info[3],'map_file_offset':info[4],'permissions':struct.pack('<I',info[5]).decode('ascii','replace'),'valid':bool(h[5]&(1<<i)),'stable':bool(h[6]&(1<<i)),'sha256':sha(actual),'expected_sha256':sha(before),'difference_count':len(differences),'first_differences':[{'relative':j,'view_offset':offset+j,'actual':actual[j],'expected':before[j]} for j in differences[:64]],'saved':str(path)})
  result={'status':h[2],'view_base':h[3],'maps_bytes':h[4],'valid_mask':h[5],'stable_mask':h[6],'compare_file_sha256':sha(expected.data),'pages':pages}
  a.decode.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return
 assert a.usr;O.mkdir(parents=True,exist_ok=True);original=ELF(a.usr/'lib/viewUnified2.so');assert sha(original.data)==VIEW_SHA
 pins='static const unsigned char a7_text_header[]={'+','.join(map(str,original.data[:52]))+'};\n';(O/'a7-text-pages-pins.h').write_text(pins)
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(O)]
 run(['arm-none-eabi-gcc',*flags,'-fPIC','-nostdlib','-shared','-Wl,-Bsymbolic','-Wl,-z,noexecstack','-Wl,--no-undefined',str(R/'payloads/a7-text-pages.c'),'-lgcc','-o',str(O/'pages.so')])
 before=ELF(a.compare);asm='.syntax unified\n.arm\n';ld='ENTRY(_start)\nSECTIONS {\n'
 for offset in OFFSETS:
  (O/f'page-{offset:x}.bin').write_bytes(before.read(offset,4096));asm+=f'.section .page_{offset:x},"ax"\n.incbin "page-{offset:x}.bin"\n';ld+=f'.page_{offset:x} {0x40000000+offset:#x} : {{ *(.page_{offset:x}) }}\n'
 asm+='.section .note.GNU-stack,"",%progbits\n';(O/'native.S').write_text(asm)
 ld+='''. = 0x70000000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) }
.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }
}
''';(O/'test.ld').write_text(ld)
 (O/'start.S').write_bytes((R/'.lab/native-inspect/start.S').read_bytes())
 run(['arm-none-eabi-gcc',*flags,'-DA7_TEXT_PAGES_TEST','-nostdlib','-T','test.ld','start.S','native.S',str(R/'payloads/a7-text-pages.c'),str(R/'research/native_text_pages_harness.c'),'-lgcc','-o','pages-test.elf'],cwd=O)
 t=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/pages-test.elf,cpu-num=0'],capture_output=True,timeout=15)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='');assert b'NATIVE_TEXT_PAGES_PASSED' in log and b'FAIL ' not in log
 sources=['payloads/a7-text-pages.c','research/native_text_pages.py','research/native_text_pages_harness.c']
 proof={'payload_sha256':sha((O/'pages.so').read_bytes()),'source_sha256':{s:sha((R/s).read_bytes()) for s in sources},'pins_sha256':sha(pins.encode()),'view_original_sha256':VIEW_SHA,'fixture_view_sha256':sha(before.data),'page_offsets':list(OFFSETS),'report_bytes':12388,'report_name':'a7pages.bin','qemu_log_sha256':sha(log),'scope':'Read-only whole snapshots of three fixed private RX pages with exact file-offset provenance; no dlopen, native calls or memory mutation','camera_execution':False}
 (O/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('payload_sha256',proof['payload_sha256'])
if __name__=='__main__':main()
