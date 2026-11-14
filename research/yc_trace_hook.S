.syntax unified
.arm
.text
.balign 4
.global a7yc_hook
.type a7yc_hook,%function
/* v9: observe all calls (including unsuccessful and small-image calls).
 * Keep first 127 successful records plus a separate largest YC example.
 * mode 0 = GetEntry_ImageSizeInfo: Entry object + 20, 60 bytes.
 * mode 1 = EncodeStill: parameter->RegionInfo, 64 bytes.
 * mode 2 = WriteStill/MakeWriteStillImage: nonnull parameter itself, 64 bytes.
 * mode 3 = their r2 StillInfo descriptor, 3400 bytes; first two records only,
 *          each at a 4096-byte stride within the same bounded allocation.
 * mode 4 = one StillInfo plus 12 bounded samples through /proc/self/mem.
 * mode 5 = AvbbcPhycMem::GetLogAddr: copy its 32-byte mapping object only.
 *          A nonzero pointer is success. No mapped pixel/MMIO read occurs.
 * mode 6 = DmmCh::open: preserve its fifth stack argument, copy the 24-byte
 *          completion, not its referenced memory. Transport and DMM status
 *          are distinct. The native caller still owns the open unit.
 * mode 7 = metadata plus one bounded read-only unit query while the original
 *          caller is still active. Keeps one record; query state is separate.
 * Modes 0-3 have no I/O. Mode 4 opens/reads/closes only /proc/self/mem.
 * No heap allocation, pixel writes or changed native return value.
 * Header is 64 bytes; each record is caller/result/mode/reserved + 64 data bytes.
 * Allocation remains alive after detach to protect in-flight calls. */
a7yc_hook:
    push {r4-r8,lr}
    mov r4,r1
    ldr r5,a7yc_state
    ldr ip,[r5,#48]
    cmp ip,#3
    movhs r4,r2
    cmp ip,#5
    moveq r4,r0
    cmp ip,#7
    movhs r4,r1
    cmp ip,#6
    bne .Lfour_args
    mov r4,r1
    ldr r8,[sp,#24]
    sub sp,sp,#8
    str r8,[sp]
    str r2,[sp,#4]
    ldr ip,[r5,#8]
    blx ip
    ldr r8,[sp,#4]
    add sp,sp,#8
    b .Lreturned
.Lfour_args:
    ldr ip,[r5,#8]
    blx ip
.Lreturned:
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
    ldr r1,[r5,#16]
    cmp r1,#1
    bne .Lunlock
    ldr r1,[r5,#32]
    adds r1,r1,#1
    strcc r1,[r5,#32]
    ldr r2,[r5,#48]
    cmp r2,#5
    beq .Lmapping_result
    cmp r0,#0
    bne .Lfailed
.Lsuccess:
    ldr r2,[r5,#48]
    cmp r2,#0
    addeq r4,r4,#20
    cmp r2,#7
    addhs r4,r4,#20
    blo .Lnot_query
    push {r0,r1}
    mov r0,r5
    mov r1,r4
    bl a7yc_dmm_observe
    pop {r0,r1}
    ldr r2,[r5,#48]
.Lnot_query:
    cmp r2,#1
    ldreq r4,[r4]
    cmp r4,#0
    beq .Lunlock
    cmp r2,#6
    streq r8,[r5,#56] /* keep request handle across a second largest record */
    /* Successful native calls retain caller-owned objects until return. */
    ldr r1,[r5,#20]
    cmp r2,#3
    moveq r3,#2
    movne r3,#127
    cmp r2,#4
    moveq r3,#1
    cmp r2,#7
    movhs r3,#1
    cmp r1,r3
    bhs .Lfull
    add r7,r5,#64
    cmp r2,#5
    bhs .Lsmall_record
    cmp r2,#3
    addhs r7,r7,r1,lsl #12 /* mode 4 only records index 0 */
    bhs .Lrecord_at
.Lsmall_record:
    /* mode 0/1/2/5 all use 80-byte records */
    add r7,r7,r1,lsl #6
    add r7,r7,r1,lsl #4
.Lrecord_at:
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
    cmp r2,#6
    beq .Ldmm_largest
    cmp r2,#0
    bne .Lunlock
    ldrh r1,[r4,#32]
    ldrh r2,[r4,#34]
    mul r3,r1,r2
.Lmeasure:
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
.Ldmm_largest:
    ldrsh r1,[r4,#2]
    cmp r1,#0
    bne .Lunlock
    ldr r3,[r4,#20]
    b .Lmeasure
.Lfailed:
    ldr r1,[r5,#36]
    adds r1,r1,#1
    strcc r1,[r5,#36]
    str r0,[r5,#40]
    b .Lunlock
.Lmapping_result:
    cmp r0,#0
    beq .Lfailed
    b .Lsuccess
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
    cmp r2,#6
    ldreq r1,[r5,#56]
    str r1,[r7],#4
    cmp r2,#0
    moveq r8,#15
    movne r8,#16
    cmp r2,#3
    movwhs r8,#850
    cmp r2,#5
    moveq r8,#8
    cmp r2,#6
    moveq r8,#6
    cmp r2,#7
    movhs r8,#15
    mov r6,r7
    mov ip,r4
.Lcopy:
    ldr r1,[ip],#4
    str r1,[r7],#4
    subs r8,r8,#1
    bne .Lcopy
    cmp r2,#4
    beq .Lsample
    cmp r2,#7
    bhs .Lmetadata_pad
    cmp r2,#5
    bhs .Lmapping_pad
    cmp r2,#0
    moveq r1,#0
    streq r1,[r7]
    bx lr
.Lmetadata_pad:
    mov r1,#0
    str r1,[r7]
    bx lr
.Lmapping_pad:
    mov r1,#0
    mov r8,#8
    cmp r2,#6
    moveq r8,#10
.Lpad:
    str r1,[r7],#4
    subs r8,r8,#1
    bne .Lpad
    bx lr
.Lsample:
    push {r0,lr}
    mov r0,r6
    mov r1,r7
    bl a7yc_sample
    pop {r0,pc}
.balign 4
.global a7yc_state
.hidden a7yc_state
.type a7yc_state,%object
a7yc_state: .word 0
.size a7yc_state,4
.size a7yc_hook,.-a7yc_hook
.weak a7yc_dmm_observe
.hidden a7yc_dmm_observe
.type a7yc_dmm_observe,%function
a7yc_dmm_observe:
    bx lr
.section .note.GNU-stack,"",%progbits
