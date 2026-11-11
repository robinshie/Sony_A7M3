/* Continue the existing per-menu-row icon initializer. Belt icons use the
 * separate index at row +24, not either of the direct image resource fields.
 * 359 is the existing slot-3 Neutral/RW family; ordinary Neutral remains 320.
 */
.syntax unified
.thumb
.section .belthook,"ax"
    b.w recipe_belt
.section .belt,"ax"
.global recipe_belt
.thumb_func
recipe_belt:
    movw r1,#359
    str.w r1,[r5,#784]
    bx lr
.section .note.GNU-stack,"",%progbits
