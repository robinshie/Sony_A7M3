#!/usr/bin/env python3
"""Check the trace decoder against original ARM metadata accessors, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.elf32 import ELF
from research.yc_trace import PINS,FIELDS

NAMES=('ImageAttach','UnitType','UnitHandle','UnitDataOffset','RecordSizeX','RecordSizeY',
       'CanvasSizeX','CanvasSizeY','ValidOffsetX','ValidOffsetY','ValidSizeX','ValidSizeY',
       'TargetOffsetX','TargetOffsetY','TargetSizeX','TargetSizeY','DataSite','Aspect',
       'YcCompress','DataTransfer','DataPlacement','DataContent','DataScan','StripWidth','YcBitDepth')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',required=True,type=Path);a=p.parse_args()
    e=ELF(a.usr/'lib/dataflowInfraFramework.so')
    digest=lambda b:hashlib.sha256(b).hexdigest()
    if digest(e.data)!=PINS['dataflowInfraFramework.so']:raise ValueError('Unexpected metadata library')
    out=ROOT/'.lab/yc-metadata-fixture';out.mkdir(parents=True,exist_ok=True)
    arrays=[];rows=[]
    for i,(field,native) in enumerate(zip(FIELDS,NAMES,strict=True)):
        matches=[s for n,s in e.symbols.items() if 'C_DataflowInfra_Entry_ImageSizeInfo' in n and f'GetData_{native}EP' in n]
        if len(matches)!=1:raise ValueError('Ambiguous accessor '+native)
        s=matches[0];code=e.read(s['value']&~1,s['size'])
        if len(code)>16:raise ValueError('Unexpected scalar accessor size')
        arrays.append(f'static const unsigned char code{i}[] __attribute__((aligned(4)))={{'+','.join(map(str,code))+'};')
        offset,size=FIELDS[field];rows.append(f'{{code{i},{offset},{size}}}')
    all_matches=[s for n,s in e.symbols.items() if 'C_DataflowInfra_Entry_ImageSizeInfo' in n and 'GetData_AllEP' in n]
    if len(all_matches)!=1:raise ValueError('Ambiguous bulk accessor')
    s=all_matches[0];code=e.read(s['value']&~1,s['size'])
    arrays.append('static const unsigned char all_code[] __attribute__((aligned(4)))={'+','.join(map(str,code))+'};')
    source='''#include <stdint.h>
static uint32_t object[20],output[17];
static unsigned checks;
static void put(const char*s){volatile unsigned*u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL YC_METADATA\n");stop();}}
'''.replace('YC_METADATA\n','YC_METADATA\\n')
    source+='\n'.join(arrays)+'\nstatic const struct {const unsigned char *code;unsigned offset,size;} fields[]={'+','.join(rows)+'};\n'
    source+='''void guest_main(void){
 for(unsigned pattern=0;pattern<256;pattern++){
  for(unsigned i=0;i<80;i++)((unsigned char*)object)[i]=(unsigned char)(pattern*131+i*17);
  for(unsigned i=0;i<sizeof fields/sizeof fields[0];i++){
   for(unsigned j=0;j<17;j++)output[j]=0xdeadbeef;
   ((void(*)(void*,void*))((uintptr_t)fields[i].code+1))(object,output+1);
   for(unsigned j=0;j<fields[i].size;j++)check(((unsigned char*)output)[4+j]==((unsigned char*)object)[20+fields[i].offset+j]);
   for(unsigned j=4+fields[i].size;j<sizeof output;j++)check(((unsigned char*)output)[j]==((unsigned char*)output)[j%4]);
   check(output[0]==0xdeadbeef);
  }
  for(unsigned j=0;j<17;j++)output[j]=0xdeadbeef;
  ((void(*)(void*,void*))((uintptr_t)all_code+1))(object,output+1);
  for(unsigned j=0;j<60;j++)check(((unsigned char*)output)[4+j]==((unsigned char*)object)[20+j]);
  check(output[0]==0xdeadbeef&&output[16]==0xdeadbeef);
 }
 put("YC_METADATA_ACCESSORS_PASSED checks=");number(checks);put("\\n");
 put("STRUCTURE_OFFSETS_ONLY; NO_CAMERA_FRAME_EXPORTED\\n");stop();
}
'''
    (out/'fixture.c').write_text(source)
    (out/'fixture.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }\n')
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-O2','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-nostdlib','-T',str(out/'fixture.ld'),str(ROOT/'ui/start.S'),str(out/'fixture.c'),'-lgcc','-o',str(out/'fixture.elf')],check=True)
    t=subprocess.run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/fixture.elf,cpu-num=0'],check=True,capture_output=True,timeout=15)
    log=t.stdout+t.stderr;(out/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if b'YC_METADATA_ACCESSORS_PASSED' not in log or b'FAIL' in log:raise ValueError('Metadata offset test failed')
    (out/'proof.json').write_text(json.dumps(dict(fields=FIELDS,scalar_accessors=len(NAMES),patterns=256,
        source_sha256={n:digest((ROOT/n).read_bytes()) for n in ('research/yc_metadata_fixture.py','research/yc_trace.py','ui/start.S')},
        library_sha256=digest(e.data),qemu_log_sha256=digest(log),camera_frame_exported=False),indent=2)+'\n')
if __name__=='__main__':main()
