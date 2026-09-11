/* Microlib scatter-region handlers. mc_w.l:handlers.o records STT_FILE
 * handlers.s, unlike the neighboring C-origin memory/decompression helpers.
 * Symbolic runtime assembly, not claimed as C decompilation. Input words are
 * aligned and byte counts are multiples of four, as supplied by armlink.
 * No literal pool, embedded instructions-as-data, or padding is required.
 */
    .syntax unified
    .cpu cortex-m7
    .thumb

    .section .text.gd_runtime_copy,"ax",%progbits
    .p2align 1
    .global gd_runtime_copy
    .type gd_runtime_copy,%function
    .thumb_func
gd_runtime_copy:                 /* flash 0x0800335a..0x08003368 */
    b .Lcopy_test
.Lcopy_word:
    ldmia r0!, {r3}
    subs r2, r2, #4
    stmia r1!, {r3}
.Lcopy_test:
    cmp r2, #0
    bne .Lcopy_word
    bx lr
    .size gd_runtime_copy, .-gd_runtime_copy

/* The adjacent 0x08003368..0x0800336a null entry also originated in
 * handlers.s. Its already exact C definition remains in runtime_scatter.c;
 * do not supply a second definition or count those same bytes twice. */

    .section .text.gd_runtime_zero,"ax",%progbits
    .p2align 1
    .global gd_runtime_zero
    .type gd_runtime_zero,%function
    .thumb_func
gd_runtime_zero:                 /* flash 0x0800336a..0x08003378 */
    movs r0, #0
    b .Lzero_test
.Lzero_word:
    stmia r1!, {r0}
    subs r2, r2, #4
.Lzero_test:
    cmp r2, #0
    bne .Lzero_word
    bx lr
    .size gd_runtime_zero, .-gd_runtime_zero

    .section .note.GNU-stack,"",%progbits
