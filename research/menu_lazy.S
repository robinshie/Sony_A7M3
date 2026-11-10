/* Install on menu creation, including resumed processes. Pinned 4.04 only. */
.syntax unified
.thumb
.text
.balign 4
.global persistent_dispatch
.thumb_func
persistent_dispatch:
    cmp r1, #98
    beq 1f
    cmp r1, #96
    bhi 2f
    adr.w r3, dispatch_map
    add.w r3, r3, r1, lsl #1
    ldrb r0, [r3]
    ldrb r3, [r3,#1]
    str r3, [r2]
    bx lr
1:  movs r0, #3
    str r0, [r2]
    bx lr
2:  movs r0, #14
    bx lr
.balign 4
dispatch_map:
    .incbin "dispatch-map.bin"
.balign 4
.global menu_setup
.thumb_func
menu_setup:
    push.w {r0-r7,r12,lr}
    mov r6, r2
    ldr r0, [r6,#4]
    cmp r0, #19
    bne done
    ldr r0, [r6,#8]
    cmp r0, #97
    bne done
    movs r7, #192
    movs r0, #0
    mov.w r1, #4096
    movs r2, #3
    movs r3, #0x22
    mov.w r4, #-1
    movs r5, #0
    svc #0
    cmn.w r0, #4096
    bcs done
    cbz r0, done
    mov r5, r0
    ldr r1, [r6]
    movs r2, #190
copy_old:
    ldr r3, [r1],#4
    str r3, [r0],#4
    subs r2, #1
    bne copy_old
    ldr r1, [r6]
    adds r1, #80
    movs r2, #10
copy_neutral:
    ldr r3, [r1],#4
    str r3, [r0],#4
    subs r2, #1
    bne copy_neutral
    movs r1, #98
    str.w r1, [r5,#768]
    ldr r1, recipe_resource
    str.w r1, [r5,#772]
    str r5, [r6]
    dmb ish
    movs r1, #20
    str r1, [r6,#4]
done:
    pop.w {r0-r7,r12,lr}
    b.w 0x40bbec
.balign 4
recipe_resource: .word 0x0204ed84

/* Selection path: set the recipe before the original setter submits it.
 * Other entries retain the getter's values. r4/r7 are the original frame ABI.
 */
.global recipe_parameters
.thumb_func
recipe_parameters:
    push.w {r0-r3,r12,lr}
    ldr.w r0, [r4,#300]
    blx 0x15ed04
    cmp r0, #98
    bne parameters_done
    movs r0, #1
    str r0, [r7,#8]
    mov.w r0, #-1
    str r0, [r7,#4]
    str r0, [r7]
parameters_done:
    pop.w {r0-r3,r12,lr}
    ldr r3, [r7,#8]
    mov r1, r4
    b.w 0x5b9fbe
.global persistent_end
persistent_end:
.section .note.GNU-stack,"",%progbits
