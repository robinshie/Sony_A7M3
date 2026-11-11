/* v3 menu allocator already owns r5. Preserve its text store, then set the
 * new large and small badge IDs. All caller registers are restored by v3. */
.syntax unified
.thumb
.section .iconhook,"ax"
bl recipe_icons
.section .icons,"ax"
.global recipe_icons
.thumb_func
recipe_icons:
    str.w r1,[r5,#772]
    ldr r1,large
    str.w r1,[r5,#776]
    ldr r1,small
    str.w r1,[r5,#792]
    bx lr
.balign 4
large: .word 0x0205c049
small: .word 0x0205c04a
.section .note.GNU-stack,"",%progbits
