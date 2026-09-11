/* Architectural entry/context code, separate from reconstructed C bodies.
 * Symbols and structured literal pools replace linked absolute addresses.
 * Reset must run before a C stack/runtime exists. The context routines expose
 * SP and callee-saved registers directly; their original microlib family is
 * established by the local library comparison, not inferred from C output.
 */
.syntax unified
.thumb

.section .text.gd_runtime_entry,"ax",%progbits
.global gd_runtime_entry, gd_runtime_after_scatter
.type gd_runtime_entry,%function
.thumb_func
gd_runtime_entry:
    ldr.w sp, .Linitial_stack
    bl gd_scatter_dispatch
.type gd_runtime_after_scatter,%function
.thumb_func
gd_runtime_after_scatter:
    ldr r0, .Lboard_main
    bx r0
.Lboard_main:
    .word gd_board_main
.Linitial_stack:
    .word gd_initial_sp
.size gd_runtime_entry, .-gd_runtime_entry

/* One original reset section contains the reset body, retained weak trap
 * slots and the shared address pool. Only the default slot is a live vector
 * target in this image; the others are retained startup-template slots.
 */
.section .text.Reset_Handler,"ax",%progbits
.global Reset_Handler, Default_Handler
.type Reset_Handler,%function
.thumb_func
Reset_Handler:
    ldr r0, .Lram_base
    add.w r1, r0, #0x8000
    mov.w r2, #0
.Lclear_boot_ram:
    strd r2, r2, [r0], #8
    cmp r0, r1
    bne .Lclear_boot_ram
    ldr r0, .Lsystem_init
    blx r0
    ldr r0, .Lruntime_entry
    bx r0
.Lweak_nmi:       b .Lweak_nmi
.Lweak_hardfault: b .Lweak_hardfault
.Lweak_memfault:  b .Lweak_memfault
.Lweak_busfault:  b .Lweak_busfault
.Lweak_usage:     b .Lweak_usage
.Lweak_svcall:    b .Lweak_svcall
.Lweak_debug:     b .Lweak_debug
.Lweak_pendsv:    b .Lweak_pendsv
.Lweak_systick:   b .Lweak_systick
.type Default_Handler,%function
.thumb_func
Default_Handler:
.Ldefault_trap:
    b .Ldefault_trap
    .balign 4, 0
.Lram_base:       .word gd_boot_ram_base
.Lsystem_init:    .word SystemInit
.Lruntime_entry:  .word gd_runtime_entry
.size Reset_Handler, .-Reset_Handler

/* Integer context layout: r8-r11/lr at0..19, r4-r7 at20..35, SP at36,
 * FP-save-area cursor at40. The ABI still reserves160 bytes. In stock the
 * optional floating-point save/restore callbacks are linker-selected NOP.W.
 * Preserve that behavior; do not silently add floating-register restoration.
 */
.section .text.gd_runtime_setjmp,"ax",%progbits
.global gd_runtime_setjmp
.type gd_runtime_setjmp,%function
.thumb_func
gd_runtime_setjmp:
    stmia.w r0!, {r8-r11, lr}
    stmia r0!, {r4-r7}
    str sp, [r0], #4
    push {r0, lr}
    nop.w
    ldmia.w sp!, {r1, lr}
    stmia r1!, {r0}
    movs r0, #0
    bx lr
.size gd_runtime_setjmp, .-gd_runtime_setjmp

.section .text.gd_runtime_longjmp,"ax",%progbits
.global gd_runtime_longjmp
.type gd_runtime_longjmp,%function
.thumb_func
gd_runtime_longjmp:
    add.w r8, r0, #44
    mov r4, r1
    ldr r0, [r8, #-4]!
    nop.w
    ldr r0, [r8, #-4]!
    mov sp, r0
    movs r0, r4
    it eq
    moveq r0, #1
    ldmdb r8!, {r4-r7}
    ldmdb r8, {r8-r11, lr}
    bx lr
.size gd_runtime_longjmp, .-gd_runtime_longjmp

/* The runtime scatter dispatcher uses its own entry/continuation convention,
 * rather than a C return. Each semantic record is {source,dest,size,helper}.
 */
.section .text.gd_scatter_dispatch,"ax",%progbits
.global gd_scatter_dispatch
.type gd_scatter_dispatch,%function
.thumb_func
gd_scatter_dispatch:
    ldr r4, .Lscatter_begin
    ldr r5, .Lscatter_end
    b .Lscatter_test
.Lscatter_region:
    ldr r0, [r4, #12]
    orr r3, r0, #1
    ldmia.w r4, {r0-r2}
    blx r3
    adds r4, #16
.Lscatter_test:
    cmp r4, r5
    bcc .Lscatter_region
    bl gd_runtime_after_scatter
.Lscatter_begin: .word gd_scatter_table
.Lscatter_end:   .word gd_scatter_table_end
.size gd_scatter_dispatch, .-gd_scatter_dispatch

/* Shutdown from a handler: construct a basic exception frame and return to
 * thread mode using EXC_RETURN. This is the architectural operation expressed
 * by generic/armcm_irq.c's inline assembly, not a C business-logic substitute.
 * The current r4 occupies the frame's scratch r12 slot; r4 itself is preserved.
 * No frame is built when IPSR says we are already in thread mode.
 */
.section .text.clear_active_irq,"ax",%progbits
.global clear_active_irq
.type clear_active_irq,%function
.thumb_func
clear_active_irq:
    mrs r0, ipsr
    lsls r0, r0, #23
    it eq
    bxeq lr
    mov.w r0, #0x01000000
    mvn.w r1, #6
    push {r0}
    adr r2, .Lafter_exception_return
    push {r2}
    push {r0, r1, r2, r3, r4, lr}
    bx r1
.Lafter_exception_return:
    bx lr
.size clear_active_irq, .-clear_active_irq
