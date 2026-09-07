// ARM Cortex-M reset handler and default interrupt handler
//
// Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

// Stock builds this code from a vendor (ST-CubeIDE style) startup_*.s
// Reset_Handler: copy .data from flash, zero .bss, call SystemInit(),
// call __libc_init_array(), then hand off to main() (Klipper's
// armcm_main()).  This file reproduces that handler instruction for
// instruction so the reset vector and the code that follows it land at
// the addresses the vendor toolchain produced.

    .syntax unified
    .thumb

    .section .text.armcm_startup, "ax", %progbits
    .align 2

    .thumb_func
    .global ResetHandler
    .type ResetHandler, %function
ResetHandler:
        ldr     r0, .Lstartup_pool
        mov     sp, r0
        ldr     r0, .Lstartup_pool+4
        ldr     r1, .Lstartup_pool+8
        ldr     r2, .Lstartup_pool+12
        movs    r3, #0
        b       2f
1:      ldr     r4, [r2, r3]
        str     r4, [r0, r3]
        adds    r3, r3, #4
2:      adds    r4, r0, r3
        cmp     r4, r1
        bcc     1b
        ldr     r2, .Lstartup_pool+16
        ldr     r4, .Lstartup_pool+20
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
.Lstartup_pool:
        .word   _stack_end
        .word   _data_start
        .word   _data_end
        .word   _data_flash
        .word   _bss_start
        .word   _bss_end
    .size ResetHandler, . - ResetHandler

    .thumb_func
    .global DefaultHandler
    .type DefaultHandler, %function
DefaultHandler:
6:      b       6b
    .size DefaultHandler, . - DefaultHandler
    /* stock pads the halfword to the next word with zero, not a nop */
    .short  0
