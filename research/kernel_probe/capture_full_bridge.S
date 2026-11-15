.syntax unified
.text
.arm
.balign 4
.global a7_undef_test
.type a7_undef_test,%function
a7_undef_test:
    push {r4,lr}
    ldr ip,1f
    blx ip
    pop {r4,pc}
1: .word private_thumb_test
.thumb
.thumb_func
private_thumb_test:
    push {r4,lr}
    .balign 4
.global a7_undef_test_site
a7_undef_test_site:
    udf.w #0xa7c
    movw r0,#0x7a7c
    pop {r4,pc}

.macro BRIDGE index,target,resume
.balign 4
.global a7_bridge_\index
.type a7_bridge_\index,%function
.thumb_func
a7_bridge_\index:
    push.w {r0-r12,lr}
    mrs r2,apsr
    push {r2,r3}
    add r1,sp,#8
    movs r0,#\index
    ldr.w ip,1f
    blx ip
    pop {r2,r3}
    msr APSR_nzcvqg,r2
    pop.w {r0-r12,lr}
    ldr.w ip,2f
    blx ip
    ldr.w lr,3f
    bx lr
.balign 4
1: .word a7_multi_record
2: .word \target
3: .word \resume
.endm
BRIDGE 0,0x636fabb1,0x636facd1
BRIDGE 1,0x63a4abb9,0x636fac41
BRIDGE 2,0x63c7c033,0x636e24ed
BRIDGE 3,0x636e0681,0x636e109d
.section .note.GNU-stack,"",%progbits
