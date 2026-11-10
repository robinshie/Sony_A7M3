.syntax unified
.arm
.section .text.start, "ax"
.global _start
_start:
    cpsid if
    ldr sp, =0x01f00000
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
1:  cmp r0, r1
    strlo r2, [r0], #4
    blo 1b
    bl guest_main
2:  wfi
    b 2b
