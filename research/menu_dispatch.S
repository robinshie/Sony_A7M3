.syntax unified
.thumb
.section .text,"ax"
.balign 4
.global ram_dispatch
.thumb_func
ram_dispatch:
    push {r4,lr}
    ldr r4, trace_pointer
    ldr r0, [r4]
    adds r0, #1
    str r0, [r4]
    str r1, [r4,#4]
    cmp r1, #98
    beq recipe
    cmp r1, #96
    bhi invalid
    adr.w r3, dispatch_map
    add.w r3, r3, r1, lsl #1
    ldrb r0, [r3]
    ldrb r3, [r3,#1]
    b output
recipe:
    movs r0, #3
    movs r3, #3
output:
    str r3, [r2]
    str r0, [r4,#8]
    str r3, [r4,#12]
    pop {r4,pc}
invalid:
    movs r0, #14
    str r0, [r4,#8]
    movs r3, #255
    str r3, [r4,#12]
    pop {r4,pc}
.balign 4
dispatch_map:
    .incbin "dispatch-map.bin"
.balign 4
.global trace_pointer
trace_pointer:
    .word 0
.section .note.GNU-stack,"",%progbits
