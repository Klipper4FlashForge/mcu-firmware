// ARM Cortex-M reset handler and default interrupt handler
//
// Copyright (C) 2024  FlashForge
//
// This file may be distributed under the terms of the GNU GPLv3 license.

// The reset handler is the vendor (ST-CubeIDE style) startup_*.s sequence
// rather than Klipper's: copy .data from flash, zero .bss, call
// SystemInit(), call __libc_init_array(), then hand off to main(), which
// is Klipper's armcm_main().

    .syntax unified
    .thumb

    .section .text.armcm_startup, "ax", %progbits
    .align 2

    .thumb_func
    .global ResetHandler
    .type ResetHandler, %function
ResetHandler:
        ldr     r0, .Lstack_end
        mov     sp, r0

        // Copy .data from its load address in flash to RAM.
        ldr     r0, .Ldata_start
        ldr     r1, .Ldata_end
        ldr     r2, .Ldata_flash
        movs    r3, #0
        b       2f
1:      ldr     r4, [r2, r3]
        str     r4, [r0, r3]
        adds    r3, r3, #4
2:      adds    r4, r0, r3
        cmp     r4, r1
        bcc     1b

        // Zero .bss.
        ldr     r2, .Lbss_start
        ldr     r4, .Lbss_end
        movs    r3, #0
        b       4f
3:      str     r3, [r2, #0]
        adds    r2, r2, #4
4:      cmp     r2, r4
        bcc     3b

        bl      SystemInit
        bl      __libc_init_array
        bl      armcm_main
5:      b       5b
.Lstack_end:
        .word   _stack_end
.Ldata_start:
        .word   _data_start
.Ldata_end:
        .word   _data_end
.Ldata_flash:
        .word   _data_flash
.Lbss_start:
        .word   _bss_start
.Lbss_end:
        .word   _bss_end
    .size ResetHandler, . - ResetHandler

    .thumb_func
    .global DefaultHandler
    .type DefaultHandler, %function
DefaultHandler:
6:      b       6b
    .size DefaultHandler, . - DefaultHandler
    /* pad the halfword out to the next word with zero, not a nop */
    .short  0
