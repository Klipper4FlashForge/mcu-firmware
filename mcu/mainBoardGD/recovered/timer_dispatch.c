/* MainBoardGD SysTick dispatcher. Derived from Klipper armcm_timer.c
 * (Kevin O'Connor, GPLv3) and checked against ITCM 0x140..0x21c.
 * DWT reads and SysTick LOAD/VAL/LOAD writes remain in their observed order.
 * The unhinted C loop currently emits 224 bytes, versus stock's 220 bytes
 * including its message literal. It fits through 0x220 using the four-byte
 * stock alignment gap but is not exact: the compiler peels the initial
 * dispatch and duplicates its loop header instead of stock's continuation
 * flag at 0x168. Explicit do/while and inlined status-return helper shapes
 * canonicalized to the same 228-byte hinted baseline and were not retained.
 * GD_TIMER_TASK isolates the exact scheduler task for partial integration.
 */
#include <stdint.h>
extern uint32_t timer_repeat_until;
uint32_t sched_timer_dispatch(void);
uint8_t sched_tasks_busy(void);
uint8_t ctr_lookup_static_string(const char *);
void sched_try_shutdown(uint8_t);
void irq_disable(void);
void irq_enable(void);

static uint32_t read_time(void)
{
    return *(volatile uint32_t *)0xe0001004;
}

#ifndef GD_TIMER_TASK

static uint32_t dispatch_many(void)
{
    uint32_t repeat_until = timer_repeat_until;
    for (;;) {
        uint32_t next = sched_timer_dispatch();
        uint32_t now = read_time();
        int32_t diff = next - now;
        if (diff > 1200)
            return diff;
        if ((int32_t)(repeat_until - now) < 0) {
            if (diff < -600000)
                sched_try_shutdown(ctr_lookup_static_string("Rescheduled timer in the past"));
            if (sched_tasks_busy()) {
                timer_repeat_until = now + 60000;
                return 3000;
            }
            timer_repeat_until = repeat_until = now + 300000;
        }
        irq_enable();
        while (diff > 0)
            diff = next - read_time();
        irq_disable();
    }
}

__attribute__((aligned(16))) void SysTick_Handler(void)
{
    irq_disable();
    uint32_t diff = dispatch_many();
    *(volatile uint32_t *)0xe000e014 = diff;
    *(volatile uint32_t *)0xe000e018 = 0;
    *(volatile uint32_t *)0xe000e014 = 0;
    irq_enable();
}

#else /* GD_TIMER_TASK: separately compiled scheduler task. */

void timer_task(void)
{
    uint32_t now = read_time();
    irq_disable();
    if ((int32_t)(timer_repeat_until - now) < 0)
        timer_repeat_until = now;
    irq_enable();
}

#endif
