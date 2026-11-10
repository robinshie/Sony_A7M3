/* Reopen and remembered-selection paths only. Slot 3 + Neutral is reserved
 * for Retro Wardrobe. Leave the six-box initialization loop unchanged. */
.syntax unified
.thumb
.section .identity,"ax"
.global recipe_reverse
.thumb_func
recipe_reverse:
    cmp r1, #3
    bne stock_reverse
    cmp r2, #3
    bne stock_reverse
    push {r3,lr}
    ldr.w r0, [r0,#300]
    movs r1, #97
    blx 0x15e118
    movs r0, #98
    pop {r3,pc}
stock_reverse:
    b.w 0x5b9b70
.section .remember,"ax"
    bl recipe_reverse
.section .reopen,"ax"
    bl recipe_reverse
.section .note.GNU-stack,"",%progbits
