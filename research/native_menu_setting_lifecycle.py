"""Original SettingMenu constructor/lifecycle ordering fixture, no device operations."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def test(original,out):
 inputs={
  'setting_ctor':(0x213ec4,0x78),
  'setting_init_head':(0x21cfe4,0x21d0a2-0x21cfe4),
  'setting_init_literals':(0x21d2a4,0x48),
 }
 for name,(at,size) in inputs.items():(out/(name+'.bin')).write_bytes(original.read(at,size))
 asm='''.syntax unified
.section .factory,"ax"
.thumb
.global stock_factory
.thumb_func
stock_factory: .incbin "factory.bin"
.section .loader_a,"ax"
.incbin "menu_loader_a.bin"
.section .loader_b,"ax"
.incbin "menu_loader_b.bin"
.section .constructor,"ax"
.thumb
.incbin "setting_ctor.bin"
.section .init_head,"ax"
.thumb
.global stock_initialize
.thumb_func
stock_initialize: .incbin "setting_init_head.bin"
.section .init_stop,"ax"
b.w init_complete
.section .init_literals,"a"
.incbin "setting_init_literals.bin"
.section .text,"ax"
.thumb
.thumb_func
init_complete:
 mov r0,r5
 bl mock_init_checked
 add sp,#12
 pop.w {r4,r5,r6,r7,r8,r9,pc}
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
.section .ctor_vtable_got,"aw"
.word 0x4087b5f8
.section .init_info_got,"aw"
.word 0x12345678
.section .init_count_got,"aw"
.word mock_root_count
'''
 stubs={
  'allocate':(0x15867c,'mock_alloc','arm'),
  'base_ctor':(0x15b1a0,'mock_base','arm'),
  'widget1':(0x40da50,'mock_widget','thumb'),
  'widget2':(0x409df0,'mock_widget','thumb'),
  'widget3':(0x2a68f4,'mock_widget','thumb'),
  'ctor_final':(0x15c1d4,'mock_ctor_final','arm'),
  'zero':(0x15aa74,'mock_zero','arm'),
  'get_info':(0x159c54,'mock_info','arm'),
  'aux_ctor':(0x159a24,'mock_aux_ctor','arm'),
  'attach':(0x15826c,'mock_attach','arm'),
  'schedule':(0x15f02c,'mock_schedule','arm'),
  'select_root':(0x21854c,'mock_select_root','thumb'),
  'select_children':(0x2183f0,'mock_select_children','thumb'),
 }
 for name,(at,target,mode) in stubs.items():asm+=f'.section .{name},"ax"\n.{mode}\n'+('b.w ' if mode=='thumb' else 'b ')+target+'\n'
 asm+='.section .note.GNU-stack,"",%progbits\n';(out/'lifecycle.S').write_text(asm)
 loc={n:a for n,(a,_,_) in stubs.items()}
 loc.update(factory=0x214638,loader_a=0x5b9a7c,loader_b=0x5b9b1c,constructor=0x213ec4,
  init_head=0x21cfe4,init_stop=0x21d0a2,init_literals=0x21d2a4,dlopen_plt=0x15d958,dlsym_plt=0x15c8dc,
  dlopen_got=0x8e54dc,dlsym_got=0x8e4ff4,ctor_vtable_got=0x8e5f44,init_info_got=0x8ebdd0,init_count_got=0x8ea538)
 ld='ENTRY(_start)\nSECTIONS {\n. = 0x40200000;\n.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
 ld+=''.join(f'.{n} {at+0x40000000:#x} : {{ *(.{n}) }}\n' for n,at in sorted(loc.items(),key=lambda x:x[1]))+'}\n';(out/'lifecycle.ld').write_text(ld)
 run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-nostdlib','-T','lifecycle.ld','start.S','lifecycle.S',str(ROOT/'research/native_menu_setting_lifecycle_harness.c'),'-lgcc','-o','lifecycle.elf'],cwd=out)
 r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/lifecycle.elf,cpu-num=0'],capture_output=True,timeout=30)
 log=r.stdout+r.stderr;(out/'lifecycle.log').write_bytes(log);print(log.decode(),end='')
 if b'NATIVE_SETTING_LIFECYCLE_PASSED' not in log or b'FAIL ' in log:raise ValueError('SettingMenu lifecycle fixture failed')
 return {'qemu_log_sha256':sha(log),'original_ranges':{n:{'va':a,'size':s,'sha256':sha(original.read(a,s))} for n,(a,s) in inputs.items()},'source_sha256':{n:sha((ROOT/n).read_bytes()) for n in ['research/native_menu_setting_lifecycle.py','research/native_menu_setting_lifecycle_harness.c']},'scope':'Complete original SettingMenu C++ constructor and UserInitialize prefix through 0x21d0a0 graph init; external services and node callback mocked; not full LCD or physical MENU verification'}
