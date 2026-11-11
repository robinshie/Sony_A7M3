.syntax unified
.arm
.text
.balign 4
.global a7yc_hook
.type a7yc_hook,%function
/* v2: observe all calls (including unsuccessful and small-image calls).
 * Keep first 127 successful records plus a separate largest YC example.
 * mode 0 = GetEntry_ImageSizeInfo: Entry object + 20, 60 bytes.
 * mode 1 = EncodeStill: parameter->RegionInfo, 64 bytes.
 * No I/O, allocation, blocking, pixel writes or changed return value.
 * Header is 64 bytes; each record is caller/result/mode/reserved + 64 data bytes.
 * Allocation remains alive after detach to protect in-flight calls. */
a7yc_hook:
    push {r4-r8,lr}
    mov r4,r1
    ldr r5,a7yc_state
    ldr ip,[r5,#8]
    blx ip
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
    ldr r1,[r5,#32]
    adds r1,r1,#1
    strcc r1,[r5,#32]
    cmp r0,#0
    bne .Lfailed
    ldr r2,[r5,#48]
    cmp r2,#0
    addeq r4,r4,#20
    ldrne r4,[r4]
    /* Successful native calls retain caller-owned objects until return. */
    ldr r1,[r5,#20]
    cmp r1,#127
    bhs .Lfull
    add r7,r5,#64
    add r7,r7,r1,lsl #6
    add r7,r7,r1,lsl #4
    add r1,r1,#1
    str r1,[r5,#20]
    bl .Lrecord
    b .Llargest
.Lfull:
    ldr r1,[r5,#24]
    adds r1,r1,#1
    strcc r1,[r5,#24]
.Llargest:
    ldr r2,[r5,#48]
    cmp r2,#0
    bne .Lunlock
    ldrh r1,[r4,#32]
    ldrh r2,[r4,#34]
    mul r3,r1,r2
    cmp r3,#0
    beq .Lunlock
    ldr r1,[r5,#44]
    cmp r3,r1
    blo .Lunlock
    str r3,[r5,#44]
    movw r1,#10224  /* 64 + 127 * 80 */
    add r7,r5,r1
    bl .Lrecord
    b .Lunlock
.Lfailed:
    ldr r1,[r5,#36]
    adds r1,r1,#1
    strcc r1,[r5,#36]
    str r0,[r5,#40]
.Lunlock:
    dmb ish
    mov r2,#0
    str r2,[r5,#12]
.Ldone:
    pop {r4-r8,pc}
.Lbusy:
    clrex
    b .Ldone
.Lrecord:
    ldr r1,[sp,#20]
    str r1,[r7],#4
    str r0,[r7],#4
    ldr r2,[r5,#48]
    str r2,[r7],#4
    mov r1,#0
    str r1,[r7],#4
    cmp r2,#0
    moveq r8,#15
    movne r8,#16
    mov ip,r4
.Lcopy:
    ldr r1,[ip],#4
    str r1,[r7],#4
    subs r8,r8,#1
    bne .Lcopy
    cmp r2,#0
    moveq r1,#0
    streq r1,[r7]
    bx lr
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
