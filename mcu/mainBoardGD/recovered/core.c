/* GD32H757 interrupt and timebase primitives, reconstructed from ITCM.
 * CMSIS intrinsics describe architectural operations, not opaque code blobs.
 */
#include <stdint.h>
#include "cmsis_compiler.h"

void initial_pins_setup(void) {}
/* Upstream armcm_irq.c spellings. armclang's own __disable_irq() is the
 * arm_compat.h intrinsic that also reads PRIMASK, which stock's 4-byte
 * irq_disable does not. */
void irq_disable(void) { asm volatile("cpsid i" ::: "memory"); }
void irq_enable(void) { asm volatile("cpsie i" ::: "memory"); }
void irq_poll(void) {}
void irq_restore(uint32_t flags) { asm volatile("msr primask, %0" :: "r" (flags) : "memory"); }

uint32_t irq_save(void)
{
    uint32_t flags;
    asm volatile("mrs %0, primask" : "=r" (flags) :: "memory");
    irq_disable();
    return flags;
}

void irq_wait(void)
{
    asm volatile("cpsie i\n    nop\n    cpsid i\n" ::: "memory");
}

uint8_t timer_is_before(uint32_t first, uint32_t second)
{
    return (int32_t)(first - second) < 0;
}

uint32_t timer_read_time(void)
{
    return *(volatile uint32_t *)0xe0001004;
}

void timer_kick(void)
{
    *(volatile uint32_t *)0xe000e014 = 0; /* SysTick LOAD */
    *(volatile uint32_t *)0xe000e018 = 0; /* SysTick VAL */
    *(volatile uint32_t *)0xe000ed04 = 0x04000000; /* pend SysTick */
}

__attribute__((noreturn)) void gd_system_reset(void)
{
    /* This local CMSIS header selects GCC-style inline assembly under ATfE.
     * Use the native Arm intrinsic for the actual barrier operation: it keeps
     * both barriers around AIRCR and reproduces stock's constant scheduling. */
    __builtin_arm_dsb(15);
    volatile uint32_t *aircr = (volatile uint32_t *)0xe000ed0c;
    *aircr = (*aircr & 0x700) | 0x05fa0004;
    __builtin_arm_dsb(15);
    for (;;) __NOP();
}
