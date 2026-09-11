/* Four isolated source probes; not the firmware's full translation units.
 * Stock addresses and byte ranges are in tools/check-gd-toolchain.py.
 * All motor offsets are bytes. The duration unit remains unresolved.
 */
#include <stddef.h>
#include <stdint.h>

struct motor {
    float electrical[4];
    float run, hold, decrement;
    uint8_t other[0x94 - 0x1c];
    uint32_t transition_ticks;
};
_Static_assert(offsetof(struct motor, run) == 0x10, "run offset");
_Static_assert(offsetof(struct motor, hold) == 0x14, "hold offset");
_Static_assert(offsetof(struct motor, decrement) == 0x18, "decrement offset");
_Static_assert(offsetof(struct motor, transition_ticks) == 0x94,
               "transition offset");

uint8_t timer_is_before(uint32_t first, uint32_t second)
{
    return (int32_t)(first - second) < 0;
}

uint32_t timer_read_time(void)
{
    return *(volatile uint32_t *)0xe0001004;
}

void set_hold_current(struct motor *motor, float hold)
{
    /* Stock uses numeric min (VMINNM), including its NaN behavior. */
    hold = __builtin_fminf(motor->run, hold);
    motor->hold = hold;
    float delta = motor->run - hold;
    motor->decrement = motor->transition_ticks
        ? delta / (float)motor->transition_ticks * 5000.0f : delta;
}

void set_run_current(struct motor *motor, float run)
{
    motor->run = run;
    float delta = run - motor->hold;
    motor->decrement = motor->transition_ticks
        ? delta / (float)motor->transition_ticks * 5000.0f : delta;
}
