/* SettingMenu factory + still-view-entry loader. B.W at the function entry preserves
 * the application's original LR. Module mode=1 must ignore the second argument
 * and run only boot reconciliation; mode=0 may install menu objects. */
.syntax unified
.thumb
.section .restore_global_hook,"ax"
bl 0x20cda0
.section .setting_hook,"ax"
bl native_menu_loader
.section .boot_hook,"ax"
b.w native_menu_boot_loader
.section .menu_loader_a,"ax"
.global native_menu_loader
.thumb_func
native_menu_loader:
 push {r0,r1,r4,r5,r6,lr}
 movs r6,#0
.Lcommon:
 ldr r4,.Lbase_delta
1: add r4,pc
 ldr r0,.Lpath_va
 add r0,r4
 movs r1,#2
 blx 0x15d958
 cmp r0,#0
 beq.w .Lfinish
 b.w .Lresolve
.balign 4
.Lbase_delta: .word -0x5b9a86
.Lpath_va: .word .Lpath
.global native_menu_boot_loader
.thumb_func
native_menu_boot_loader:
 push {r0,r1,r4,r5,r6,lr}
 movs r6,#1
 b.w .Lcommon
.section .menu_loader_b,"ax"
.Lresolve:
 ldr r1,.Lsymbol_va
 add r1,r4
 blx 0x15c8dc
 cbz r0,.Lfinish
 mov r3,r0
 mov r0,r4
 ldr r1,[sp,#4]
 mov r2,r6
 blx r3
.Lfinish:
 cmp r6,#1
 bne .Lmenu_finish
 pop.w {r0,r1,r4,r5,r6,lr}
 /* Reproduce the stolen prologue AFTER restoring the original application LR. */
 push {r3,r4,r7,lr}
 add r7,sp,#0
 b.w 0x188af0
.Lmenu_finish:
 pop.w {r0,r1,r4,r5,r6,lr}
 b.w 0x213ec4
.balign 4
.Lsymbol_va:.word .Lsymbol
.Lpath:.asciz "/usr/lib/a7fl.so"
.Lsymbol:.asciz "a7_fl_install"
.balign 2
.section .note.GNU-stack,"",%progbits
