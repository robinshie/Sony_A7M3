.syntax unified
.arm
.text
.balign 4
.global a7yc_hook
.type a7yc_hook,%function
/* Bounded metadata recorder around GetEntry_ImageSizeInfo. Calls the original
 * once, preserves its result, copies only its successful 60-byte output, and
 * does no I/O, allocation, waiting or pixel write. The installer retains this
 * allocation even after detach, so in-flight calls never reference freed code.
 * Header: magic, version, original, lock, armed, count, dropped, max=128.
 * Records: caller LR followed by PIN_YC_IMAGE_SIZE_INFO (60 bytes). */
a7yc_hook:
    push {r4-r8,lr}
    mov r4,r1
    ldr r5,a7yc_state
    ldr ip,[r5,#8]
    blx ip
    cmp r0,#0
    bne .Ldone
    /* Skip small preview/thumbnail metadata so the bounded log is still
     * available when a full-size photograph is taken. This is a size filter,
     * not proof that the remaining records belong to the capture path. */
    ldrh r1,[r4,#0x34]
    movw r2,#2800
    cmp r1,r2
    blo .Ldone
    ldrh r1,[r4,#0x36]
    movw r2,#1800
    cmp r1,r2
    blo .Ldone
    ldr r1,[r5,#16]
    cmp r1,#1
    bne .Ldone
    add r6,r5,#12
    ldrex r2,[r6]
    cmp r2,#0
    bne .Lbusy
    mov r3,#1
    strex r2,r3,[r6]
    cmp r2,#0
    bne .Ldone
    dmb ish
    ldr r1,[r5,#20]
    cmp r1,#128
    bhs .Lfull
    add r7,r5,#32
    add r7,r7,r1,lsl #6
    ldr r2,[sp,#20]
    str r2,[r7],#4
    add r4,r4,#20
    mov r8,#15
.Lcopy:
    ldr r2,[r4],#4
    str r2,[r7],#4
    subs r8,r8,#1
    bne .Lcopy
    add r1,r1,#1
    str r1,[r5,#20]
    b .Lunlock
.Lfull:
    ldr r1,[r5,#24]
    adds r1,r1,#1
    strcc r1,[r5,#24]
.Lunlock:
    dmb ish
    mov r2,#0
    str r2,[r6]
.Ldone:
    pop {r4-r8,pc}
.Lbusy:
    clrex
    b .Ldone
.balign 4
.global a7yc_state
.hidden a7yc_state
.type a7yc_state,%object
a7yc_state: .word 0
.size a7yc_state,4
.global a7yc_hook_end
a7yc_hook_end:
.size a7yc_hook,.-a7yc_hook
.section .note.GNU-stack,"",%progbits
