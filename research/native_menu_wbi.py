#!/usr/bin/env python3
"""Build/test a read-only WBI head diagnostic. Never accesses a camera."""
import hashlib,json,subprocess,struct,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.lab/native-wbi'
FLAGS=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'research')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)
def decode(raw):
 if len(raw)!=1112:raise ValueError('Expected 1112-byte WBI report')
 names='magic version phase status error pid capacity_lo capacity_hi mode header_kind written fsync_ok neighbor_ok reserved'.split()
 h=dict(zip(names,struct.unpack('<3I2i9I',raw[:56])))
 if h['magic']!=0x57423741 or h['version']!=1 or h['reserved'] or h['mode']>1:raise ValueError('Bad report header')
 h['preimage_sha256']=raw[56:88].hex();h['header_sha256']=hashlib.sha256(raw[88:600]).hexdigest();h['neighbor_sha256']=hashlib.sha256(raw[600:1112]).hexdigest()
 if h['phase']>=3 and hashlib.sha256(raw[88:1112]).hexdigest()!=h['preimage_sha256']:raise ValueError('Report preimage digest differs')
 return h
def build():
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
 (OUT/'entry.c').write_text('''#include "native_menu_wbi.h"
extern long nma_linux_syscall(void*,long,long,long,long,long,long,long);
static NwbReport r;
__attribute__((constructor)) static void entry(void){long fd=nma_linux_syscall(0,5,(long)"/tmp/jiritsu/a7wbi.bin",1|64|128,0600,0,0,0);if(fd<0)return;nwb_run(nma_linux_syscall,0,0,0,&r);unsigned done=0;while(done<sizeof r){long n=nma_linux_syscall(0,4,fd,(long)((unsigned char*)&r+done),sizeof r-done,0,0,0);if(n<=0)break;done+=(unsigned)n;}nma_linux_syscall(0,118,fd,0,0,0,0,0);nma_linux_syscall(0,6,fd,0,0,0,0,0);}
''')
 for n,p in [('core',ROOT/'research/native_menu_wbi.c'),('linux',ROOT/'research/native_menu_activate_linux.c'),('entry',OUT/'entry.c')]:run(['arm-none-eabi-gcc',*FLAGS,'-fPIC','-c',str(p),'-o',str(OUT/(n+'.o'))])
 run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',*[str(OUT/(n+'.o')) for n in ('core','linux','entry')],'-o',str(OUT/'probe.so')])
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
 (OUT/'guest.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x40200000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }\n')
 run(['arm-none-eabi-gcc',*FLAGS,'-nostdlib','-T',str(OUT/'guest.ld'),str(OUT/'start.S'),str(ROOT/'research/native_menu_wbi_harness.c'),'-lgcc','-o',str(OUT/'test.elf')])
 r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','256','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/test.elf,cpu-num=0'],capture_output=True,timeout=30)
 log=r.stdout+r.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
 if b'NWB_ARM_ALL_PASS' not in log or b'NWB_FAIL' in log:raise ValueError('WBI core fixture failed')
 src=['research/native_menu_wbi.h','research/native_menu_wbi.c','research/native_menu_wbi.py','research/native_menu_wbi_harness.c','research/native_menu_activate_linux.c','payloads/sha256.h']
 proof={'payload_sha256':sha(OUT/'probe.so'),'payload_bytes':(OUT/'probe.so').stat().st_size,'report_path':'/tmp/jiritsu/a7wbi.bin','report_bytes':1112,'mode':0,'write_payload_built':False,'source_sha256':{n:sha(ROOT/n) for n in src},'qemu_log_sha256':sha(OUT/'qemu.log'),'scope':'Exact ARM core with modeled block-device syscalls and fault injection; deployment constructor hardcoded mode zero; no actual device writes or camera test'}
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');return proof
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decode',type=Path);a=p.parse_args();print(json.dumps(decode(a.decode.read_bytes()) if a.decode else build(),indent=2))
