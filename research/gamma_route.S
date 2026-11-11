/* Test adapters for unchanged native basic blocks, never a camera payload.
 * Exit trampolines are outside the extracted instruction ranges.
 */
.syntax unified
.thumb
.equ AVCAM,0x635c6000
.section .text.adapters,"ax"
.global route_bridge
.thumb_func
route_bridge:
    push {r4-r8,lr}
    mov r5,r0
    mov r4,r1
    ldr r6,=AVCAM+0x118d8b4
    ldr ip,=AVCAM+0x5e797b
    bx ip
.global route_bridge_return
.thumb_func
route_bridge_return:
    pop {r4-r8,pc}

.global route_descriptor
.thumb_func
route_descriptor:
    push {r4,r5,r6,lr}
    mov r4,r0
    mov r5,r1
    ldr ip,=AVCAM+0x7f8a3d
    bx ip
.global route_descriptor_return
.thumb_func
route_descriptor_return:
    pop {r4,r5,r6,pc}

.global route_forward
.thumb_func
route_forward:
    push {r4,r5,r6,lr}
    mov r4,r0
    mov r5,r1
    mov r3,r2
    movw r1,#0x1357
    ldr ip,=AVCAM+0x5e008b
    bx ip
.global route_forward_return
.thumb_func
route_forward_return:
    pop {r4,r5,r6,pc}
.section .note.GNU-stack,"",%progbits
