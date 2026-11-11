/* Two pinned NOP caves in the already-verified RW image.  No code is stolen.
 * Called instead of the original ViewGlobalMenu constructor.  Every path
 * restores its arguments and tail-calls that original constructor. */
.syntax unified
.thumb
.section .menu_hook,"ax"
bl native_menu_loader

.section .menu_loader_a,"ax"
.global native_menu_loader
.thumb_func
native_menu_loader:
 push {r0,r1,r4,r5,r6,lr}
 ldr r4, .Lbase_delta
1: add r4, pc
 ldr r0, .Lpath_va
 add r0, r4
 movs r1, #2
 blx 0x15d958 /* original ARM PLT: preserves lazy binding ABI */
 cmp r0, #0
 beq.w .Lfinish
 b.w .Lresolve
.balign 4
.Lbase_delta: .word -0x5b9a84 /* pinned PC at the add above */
.Lpath_va: .word .Lpath

.section .menu_loader_b,"ax"
.Lresolve:
 ldr r1, .Lsymbol_va
 add r1, r4
 blx 0x15c8dc /* original ARM PLT */
 cbz r0, .Lfinish
 mov r3, r0
 mov r0, r4
 ldr r1, [sp,#4]
 blx r3
.Lfinish:
 pop.w {r0,r1,r4,r5,r6,lr}
 b.w 0x20cda0
.balign 4
.Lsymbol_va: .word .Lsymbol
.Lpath: .asciz "/usr/lib/a7fl.so"
.Lsymbol: .asciz "a7_fl_install"
.balign 2
.section .note.GNU-stack,"",%progbits
