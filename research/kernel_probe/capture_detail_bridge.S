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
    udf.w #0xa76
    movw r0,#0x7a76
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
BRIDGE 0,0x6391a895,0x638fb891
BRIDGE 1,0x636de0b9,0x636e0df5
BRIDGE 2,0x63d8848d,0x63aad0e5
BRIDGE 3,0x63d83e2f,0x63a22e5d
.section .note.GNU-stack,"",%progbits
