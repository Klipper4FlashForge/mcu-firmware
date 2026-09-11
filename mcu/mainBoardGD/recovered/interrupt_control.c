/* GD32 system-route SDK function (the NVIC ones are lib/gd32h7xx misc.c).
 * Preserve raw word arguments, key writes, byte priority stores and each
 * volatile clear/reload/OR operation. There are no inferred range checks.
 */
#include "mclib_hardware.h"

void gd_motor_syscfg_route(uint32_t source, uint32_t destination)
{
    volatile uint32_t *route = (volatile uint32_t *)(uintptr_t)(0x40018400u | (source & 0xfc));
    if (*route & 0x80000000u)
        return;
    uint32_t shift = (source << 3) & 24;
    *route &= ~(0xffu << shift);
    *route |= destination << shift;
}
