#!/usr/bin/env python3
"""Pin the native confirmation ABI and execute its lifecycle in ARM QEMU.

Widgets, the renderer and EventManager are modeled. No USB/device writes.
"""
import argparse, hashlib, json, subprocess
from pathlib import Path
from elf32 import ELF
from creative_dispatch import VIEW_SHA
R=Path(__file__).resolve().parents[1]; O=R/'.lab/native-save-dialog'
BASE={2:0x40000000,6:0x42000000,0:0x44000000}
PIECES={6:[(0x1a7f8,8),(0x43798,0x64),(0x437fc,0x3c),(0x4391e,0x24),
           (0x4394c,0x142),(0x43a8e,6),(0x43a94,0x80),(0x43b14,0x2e),
           (0x42b6e,0x26),(0x6edd5,6)],
        0:[(0x12fdcc,0xdc)]}
def sha(b):return hashlib.sha256(b).hexdigest()
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',type=Path,required=True);a=p.parse_args()
    e={i:ELF(a.usr/'lib'/n) for i,n in [(2,'viewUnified2.so'),(6,'viewUnified6.so'),(0,'libObj.so')]}
    if sha(e[2].data)!=VIEW_SHA:raise ValueError('Foreign view2')
    # These identities are recorded from the project's pinned 4.04 extraction.
    for i,h in PINNED.items():
        if sha(e[i].data)!=h:raise ValueError('Foreign dialog input')
    O.mkdir(parents=True,exist_ok=True);(O/'proof.json').unlink(missing_ok=True)
    ranges={2:[(0x15bf38,12),(0x15d958,12),(0x15c8dc,12),(0x587be8,12),(0x580994,12),
               (0x2a8c80,24),(0x587ac6,16),(0x58060a,16)],
            6:[(0x437fc,0x3c),(0x4391e,0x24),(0x43798,0x64),(0x43a5c,0x32),
               (0x43b14,0x2e),(0x43a94,0x80),(0x42b6e,0x26),(0x1a7f8,8)],
            0:[(0x12fdcc,0xdc),(0x12fd08,24),(0x12e4a8,24),(0x155656,24),
               (0x10d26a,24),(0x862868,14)]}
    header='struct a7_dialog_pin {unsigned library,offset,size;const unsigned char *bytes;};\n';records=[]
    for lib,items in ranges.items():
        for offset,size in items:
            if any(offset<=v<offset+size for v in e[lib].relocations):raise ValueError('Relocation in pin')
            name=f'a7_dialog_pin_{lib}_{offset:x}';raw=e[lib].read(offset,size)
            header+=f'static const unsigned char {name}[]={{'+','.join(map(str,raw))+'};\n'
            records.append(f'{{{lib},{offset},{size},{name}}}')
    header+='#define a7_dialog_pin_dlclose a7_dialog_pin_2_15bf38\n#define a7_dialog_pin_dlopen a7_dialog_pin_2_15d958\n#define a7_dialog_pin_dlsym a7_dialog_pin_2_15c8dc\n'
    header+='static const struct a7_dialog_pin a7_dialog_pins[]={'+','.join(records)+'};\n'
    (O/'a7-fl-dialog-pins.h').write_text(header)
    asm='.syntax unified\n';sections=[];stub_records=[];stub_header=''
    def add(address,name,body,mode='ax'):
        nonlocal asm
        sections.append((address,name));asm+=f'.section .{name},"{mode}"\n'+body+'\n'
    for lib,items in PIECES.items():
        for offset,size in items:
            name=f'part_{lib}_{offset:x}';(O/(name+'.bin')).write_bytes(e[lib].read(offset,size))
            add(BASE[lib]+offset,name,f'.incbin "{name}.bin"')
    # True constructor loads the original GOT and creates both vptrs.
    vt=bytearray(364)
    import struct
    for off in range(0,364,4):
        value=e[6].word(0x839b8+off);rel=e[6].relocations.get(0x839b8+off)
        if rel and rel[0]==23:value+=BASE[6]
        struct.pack_into('<I',vt,off,value)
    (O/'vtable.bin').write_bytes(vt)
    add(BASE[6]+0x839b8,'vtable','.incbin "vtable.bin"','aw')
    add(BASE[6]+0x85630,'got','.word 0x420839b8','aw')
    stubs={
      6:{0x13f78:'base_ctor',0x13e84:'model_request',0x14314:'allocate',0x13c58:'unexpected',0x13dd8:'unexpected',
         0x1399c:'event_id',0x13f94:'close_view',0x140e0:'stock_write',0x14320:'get_highlight',0x139e8:'set_highlight',
         0x141b4:'get_widget',0x13eb4:'cast_widget',0x13a7c:'display',0x13d6c:'cast_footer',
         0x139b4:'wrap_ctor',0x13d9c:'wrap_enable',0x13d20:'wrap_destroy'},
      2:{0x587be8:'cast_widget',0x580994:'cast_widget',0x2a8c80:'set_highlight'},
      0:{0x12e4a8:'get_widget',0x155656:'display',0x10d26a:'direct_text',0x862868:'redraw',0x12fd08:'close_view',
         0x104be4:'id_get',0x100a54:'allocate',0xffefc:'event_ctor',0x108c40:'param_ctor',
         0x101b94:'event_add',0xffce0:'push_event',0x101ff0:'unexpected',0x101ecc:'unexpected',
         0x107578:'unexpected',0x121cd8:'unexpected',0x1039c8:'unexpected',0x121bae:'unexpected',
         0x121b52:'unexpected',0x121b62:'unexpected',0x103460:'unexpected'}}
    for lib,entries in stubs.items():
        for va,target in entries.items():
            thumb=(lib==2 or (lib==0 and va in (0x12e4a8,0x155656,0x10d26a,0x862868,0x12fd08,0x108c40,0x121cd8,0x121bae,0x121b52,0x121b62)))
            # Veneers accept BLX to the standard +4 ARM PLT entry too.
            body=(f'.thumb\nldr.w ip,1f\nbx ip\n.balign 4\n1: .word {target}' if thumb else
                  f'.arm\nnop\nldr pc,[pc,#-4]\n.word {target}')
            add(BASE[lib]+va,f'stub_{lib}_{va:x}',body)
            if any(off<=va<off+size for off,size in ranges.get(lib,[])):
                stub_records.append('{'+str(BASE[lib]+va)+','+str(12 if not thumb or va%4==0 else 14)+',{0}}')
    for va,slot,target in [(0x15d958,0x8e54dc,'mock_dlopen'),(0x15c8dc,0x8e4ff4,'mock_dlsym'),(0x15bf38,0x8e4d1c,'mock_dlclose')]:
        raw=e[2].read(va,12);name=f'loader_{va:x}';(O/(name+'.bin')).write_bytes(raw)
        add(BASE[2]+va,name,f'.incbin "{name}.bin"');add(BASE[2]+slot,name+'_got',f'.word {target}','aw')
    stub_header+='static struct {uintptr_t address;unsigned size;unsigned char bytes[20];} saved_stubs[]={'+','.join(stub_records)+'};\n'
    (O/'test-stubs.h').write_text(stub_header)
    asm+='.section .note.GNU-stack,"",%progbits\n';(O/'native.S').write_text(asm)
    (O/'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
 cpsid if
 ldr sp,=0x43000000
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
    ld='ENTRY(_start)\nSECTIONS {\n. = 0x41000000; .text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    ld+=''.join(f'.{n} {v:#x} : {{ *(.{n}) }}\n' for v,n in sorted(sections))+'}\n';(O/'test.ld').write_text(ld)
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror',
           '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
           '-I',str(R/'payloads'),'-I',str(O),'-DA7_FL_DIALOG_TEST']
    run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','test.ld','start.S','native.S',
         str(R/'payloads/a7-fl-dialog.c'),str(R/'research/native_save_dialog_harness.c'),'-lgcc','-o','dialog-test.elf'],cwd=O)
    t=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none',
           '-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native',
           '-device',f'loader,file={O}/dialog-test.elf,cpu-num=0'],capture_output=True,timeout=20)
    log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if b'NATIVE_SAVE_DIALOG_PASSED' not in log or b'FAIL' in log:raise ValueError('Dialog fixture failed')
    sources=['payloads/a7-fl-dialog.c','payloads/a7-fl-dialog.h','research/native_save_dialog.py','research/native_save_dialog_harness.c','research/elf32.py']
    (O/'proof.json').write_text(json.dumps(dict(source_sha256={s:sha((R/s).read_bytes()) for s in sources},
        native_sha256={str(k):sha(v.data) for k,v in e.items()},pins_sha256=sha(header.encode()),
        qemu_log_sha256=sha(log),scope=__doc__,camera_execution=False),indent=2)+'\n')
PINNED={6: '3f2e9ce62815b1673269691d9239f11f28f9230e60ae7451ad2131b15be22dbc', 0: '1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23'}
if __name__=='__main__':main()
