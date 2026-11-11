/* 4.04 Creative Style display only. The model still receives style 3/box 3.
 * PAS_BtnComboIcon owns a 24-byte item array at +3064. Replace only the
 * Neutral item's image, with an equal-sized RW resource, before the stock
 * setIndex call redraws it. Other slots restore the original Neutral image.
 */
.syntax unified
.thumb
.section .displayhook,"ax"
    bl recipe_footer
.section .count,"ax"
    mov.w ip,#13
.section .footer,"ax"
.global recipe_footer
.thumb_func
recipe_footer:
    push {r2,r3}
    ldr.w r2,[r0,#452]
    cmp r2,#13
    bne done
    ldr.w r2,[r0,#3064]
    cbz r2,done
    ldr r3,[r2,#48]
    ldr r1,neutral
    cmp r3,r1
    beq known
    ldr r1,rw
    cmp r3,r1
    bne done
known:
    ldr r1,neutral
    cmp.w fp,#3
    bne assign
    ldr r3,[r7,#60]
    cmp r3,#3
    bne assign
    ldr r1,rw
assign:
    str r1,[r2,#48]
done:
    pop {r2,r3}
    add.w r1,fp,#-1
    bx lr
.balign 4
neutral: .word 0x0205c865
rw: .word 0x0205c823
.section .note.GNU-stack,"",%progbits
