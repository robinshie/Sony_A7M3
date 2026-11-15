.syntax unified
.arm
.text
.balign 4
.global a7_undef_test
.type a7_undef_test,%function
a7_undef_test:
    push {r4,lr}
    ldr ip,3f
    blx ip
    pop {r4,pc}
3:  .word a7_undef_test_thumb
.size a7_undef_test,.-a7_undef_test
.thumb
.type a7_undef_test_thumb,%function
.thumb_func
a7_undef_test_thumb:
    push {r4,lr}
    .balign 4
.global a7_undef_test_site
a7_undef_test_site:
    udf.w #0xa73
    movw r0,#0x7a73
    pop {r4,pc}
.size a7_undef_test_thumb,.-a7_undef_test_thumb

/* Entered by exception return at the aligned native BL to mark_stage.
 * The original stage prologue and get_context call have already executed.
 * Return to the instruction following that BL, not the interrupted LR. */
.balign 4
.global a7_jpeg_bridge
.type a7_jpeg_bridge,%function
.thumb_func
a7_jpeg_bridge:
    push.w {r0-r3,r12,lr}
    mrs r2,apsr
    push {r2,r3}
    ldr.w ip,3f
    blx ip
    pop {r2,r3}
    msr APSR_nzcvqg,r2
    pop.w {r0-r3,r12,lr}
    ldr.w ip,1f
    blx ip
    ldr.w pc,2f
.balign 4
1: .word 0x63d3bb01 /* original mark_stage */
2: .word 0x639061a1 /* original stage continuation */
3: .word a7_jpeg_record
.size a7_jpeg_bridge,.-a7_jpeg_bridge
.section .note.GNU-stack,"",%progbits
