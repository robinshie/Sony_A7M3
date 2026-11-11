#!/usr/bin/env python3
"""Build read-only resident inspection; execute pinned native accessors in QEMU."""
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
from elf32 import ELF
from creative_dispatch import VIEW_SHA
R=Path(__file__).resolve().parents[1]
O=R/'.lab/native-inspect'
def sha(data): return hashlib.sha256(data).hexdigest()
def run(args, **kw): return subprocess.run(args, check=True, **kw)
def main():
 p=argparse.ArgumentParser();p.add_argument('--usr',type=Path,required=True)
 p.add_argument('--module',type=Path,default=R/'.lab/native-module/liba7-fl-module.so')
 p.add_argument('--bundle',type=Path,default=R/'.lab/native-fl-01');a=p.parse_args()
 O.mkdir(parents=True,exist_ok=True)
 proof_path=a.module.parent/'proof.json';mp=json.loads(proof_path.read_text());module=ELF(a.module)
 assert mp['module_sha256']==sha(module.data) and mp['ready_for_staging'] and not mp['placeholder']
 for name,digest in mp['source_sha256'].items(): assert sha((R/name).read_bytes())==digest,name
 for name,digest in mp['dependency_proof_sha256'].items():
  dependency=R/'.lab'/name;assert sha(dependency.read_bytes())==digest,name
  for path,value in json.loads(dependency.read_text())['source_sha256'].items():assert sha((R/path).read_bytes())==value,path
 data=(a.module.parent/'a7-fl-module-data.h').read_bytes()
 assert sha(data)==mp['artifact_sha256']['a7-fl-module-data.h']
 def array(name):
  match=re.search(r'\b'+name+r'(?:\[\d+\])+\s*=\s*\{(.*?)\};',data.decode(),re.S)
  assert match,name
  assert re.fullmatch(r'[\s\d,{}]*',match[1]),name
  return list(map(int,re.findall(r'\d+',match[1])))
 original=array('a7_pkg_original');base=bytes(array('a7_pkg_base'))
 codec=struct.pack('<129H',*array('a7_pkg_expand'))+bytes(array('a7_pkg_compress'))
 assert len(original)==5120 and len(base)==1280 and len(codec)==771
 originals={f'{0x30004+i:08x}':bytes(original[i*1280:(i+1)*1280]) for i in range(4)}
 for name,b in originals.items(): assert (a.bundle/(name+'.bin')).read_bytes()==b,name
 assert (a.bundle/'candidate.bin').read_bytes()==base and (a.bundle/'codec.bin').read_bytes()==codec
 view=ELF(a.usr/'lib/viewUnified2.so');assert sha(view.data)==VIEW_SHA
 parts={'dlopen':(0x15d958,0x8e54dc),'dlsym':(0x15c8dc,0x8e4ff4),'dlclose':(0x15bf38,0x8e4d1c)}
 pins='#include <stdint.h>\n'
 def pin(name,b): return 'static const unsigned char a7_inspect_'+name+'[]={'+','.join(map(str,b))+'};\n'
 for name,(address,_) in parts.items():
  b=view.read(address,12);pins+=pin(name,b);(O/(name+'.bin')).write_bytes(b)
 pins+=pin('module_header',module.data[:52])
 for short,name in [('boot','a7_fl_bootstrap_status'),('runtime','a7_fl_status')]:
  symbol=module.symbols[name];pins+=pin(short+'_code',module.read(symbol['value']&~1,symbol['size']))
  pins+=f'static const uint32_t a7_inspect_{short}_va={symbol["value"]}u;\n'
 rw=[s for s in module.segments if s[0]==1 and s[6]==6];assert len(rw)==1
 rx=[s for s in module.segments if s[0]==1 and s[6]==5];assert len(rx)==1 and rx[0][2]==0
 rx_hi=(rx[0][4]+4095)&~4095;rw_lo=rw[0][2]&~4095;rw_file_hi=(rw[0][2]+rw[0][4]+4095)&~4095;rw_hi=(rw[0][2]+rw[0][5]+4095)&~4095
 assert rx_hi<=rw_lo and rw_lo<rw_file_hi<=rw_hi
 rx_map=f'60000000-{0x60000000+rx_hi:08x} r-xp 00000000 00:01 2 /usr/lib/a7fl.so\n'
 all_maps=rx_map+f'{0x60000000+rw_lo:08x}-{0x60000000+rw_file_hi:08x} rw-p {rw[0][1]&~4095:08x} 00:01 2 /usr/lib/a7fl.so\n'
 if rw_file_hi<rw_hi:all_maps+=f'{0x60000000+rw_file_hi:08x}-{0x60000000+rw_hi:08x} rw-p 00000000 00:00 0\n'
 pins+='#define A7_INSPECT_TEST_MODULE_MAPS '+json.dumps(all_maps)+'\n#define A7_INSPECT_TEST_MODULE_RX '+json.dumps(rx_map)+'\n'
 pins+=f'static const uint32_t a7_inspect_rw_begin={rw[0][2]}u,a7_inspect_rw_end={rw[0][2]+rw[0][5]}u;\n'
 (O/'a7-fl-inspect-pins.h').write_text(pins)
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(R/'payloads'),'-I',str(R/'research'),'-I',str(O)]
 run(['arm-none-eabi-gcc',*flags,'-fPIC','-nostdlib','-shared','-Wl,-z,noexecstack','-Wl,--no-undefined',str(R/'payloads/a7-fl-inspect.c'),'-lgcc','-o',str(O/'inspect.so')])
 (O/'module-rx.bin').write_bytes(module.read(0,rx[0][4]))
 asm='.syntax unified\n.arm\n'
 ld='ENTRY(_start)\nSECTIONS {\n'
 for name,(address,got) in parts.items():
  asm+=f'.section .{name},"ax"\n.incbin "{name}.bin"\n.section .got_{name},"aw"\n.word mock_{name}\n'
  ld+=f'.{name} {0x40000000+address:#x} : {{ *(.{name}) }}\n.got_{name} {0x40000000+got:#x} : {{ *(.got_{name}) }}\n'
 asm+='.section .module,"ax"\n.incbin "module-rx.bin"\n.section .note.GNU-stack,"",%progbits\n'
 ld+=f'.module 0x60000000 : {{ *(.module) }}\n.module_data {0x60000000+rw_lo:#x} (NOLOAD) : {{ . += {rw_hi-rw_lo:#x}; }}\n'
 ld+='''
 . = 0x70000000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) }
 .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }
}
'''
 (O/'native.S').write_text(asm);(O/'test.ld').write_text(ld)
 (O/'start.S').write_text('''.syntax unified
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
.section .note.GNU-stack,"",%progbits
''')
 run(['arm-none-eabi-gcc',*flags,'-DA7_FL_INSPECT_TEST','-nostdlib','-T','test.ld','start.S','native.S',str(R/'payloads/a7-fl-inspect.c'),str(R/'research/native_inspect_harness.c'),'-lgcc','-o','inspect-test.elf'],cwd=O)
 t=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/inspect-test.elf,cpu-num=0'],capture_output=True,timeout=15)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='');assert b'NATIVE_INSPECT_PASSED' in log and b'FAIL ' not in log
 sources=['payloads/a7-fl-inspect.c','payloads/a7-fl-inspect.h','payloads/a7-fl-module.h','payloads/a7-fl-bootstrap.h','research/native_inspect.py','research/native_inspect_harness.c']
 proof={'payload_sha256':sha((O/'inspect.so').read_bytes()),'module_sha256':sha(module.data),'module_proof_sha256':sha(proof_path.read_bytes()),'source_sha256':{s:sha((R/s).read_bytes()) for s in sources},'original_lut_sha256':{k:sha(v) for k,v in originals.items()},'original_sha256':sha(originals['00030004']),'base_fl_sha256':sha(base),'codec_sha256':sha(codec),'build':re.search(r'a7_pkg_build\[24\]="([^"]+)"',data.decode())[1],'pins_sha256':sha(pins.encode()),'qemu_log_sha256':sha(log),'report_bytes':148,'report_path':'/tmp/jiritsu/a7status.bin','scope':'Original view dlopen/dlsym/dlclose PLTs and exact staged-module status accessors execute in QEMU with modeled loader and proc files; no module initialization or persistent mutation.','camera_execution':False}
 (O/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('payload_sha256:',proof['payload_sha256'])
if __name__=='__main__': main()
