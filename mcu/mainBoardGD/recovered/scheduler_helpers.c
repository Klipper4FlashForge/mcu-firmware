/* mainBoardGD scheduler primitives, derived from Klipper sched.c (GPLv3).
 * Names describe stock globals split between initialized and zeroed regions.
 */
#include <stdint.h>
#include "state.h"
#include "generated/generated.h"

struct task_wake { volatile uint8_t wake; };
extern int8_t tasks_status;
extern uint8_t shutdown_status;
extern uint32_t timer_from_us(uint32_t usecs);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);

uint_fast8_t deleted_event(struct timer *timer)
{
    (void)timer;
    return 0;
}

void sched_wake_tasks(void) { tasks_status = 0; }
uint8_t sched_tasks_busy(void) { return tasks_status >= 0; }
uint8_t sched_is_shutdown(void) { return !!shutdown_status; }

void sched_wake_task(struct task_wake *wake)
{
    sched_wake_tasks();
    /* Klipper writeb(): compiler memory barrier before the volatile store. */
    __asm__ __volatile__("" ::: "memory");
    wake->wake = 1;
}

uint8_t sched_check_wake(struct task_wake *wake)
{
    /* Klipper readb() orders subsequent accesses after this volatile load. */
    uint8_t ready = wake->wake;
    __asm__ __volatile__("" ::: "memory");
    if (!ready)
        return 0;
    __asm__ __volatile__("" ::: "memory");
    wake->wake = 0;
    return 1;
}

/* Upstream marks this helper always-inline while retaining an external body. */
extern inline __attribute__((always_inline))
void sched_try_shutdown(uint_fast8_t reason)
{
    if (!shutdown_status)
        sched_shutdown(reason);
}

uint_fast8_t periodic_event(struct timer *timer)
{
    (void)timer;
    sched_wake_tasks();
    periodic_timer.waketime += timer_from_us(100000);
    sentinel_timer.waketime = periodic_timer.waketime ^ 0x80000000u;
    return 1;
}

uint_fast8_t sentinel_event(struct timer *timer)
{
    (void)timer;
    sched_shutdown(ctr_lookup_static_string("sentinel timer called"));
}

void sched_clear_shutdown(void)
{
    if (shutdown_status == 2)
        return;
    if (!shutdown_status)
        sched_shutdown(ctr_lookup_static_string("Shutdown cleared when not shutdown"));
    shutdown_status = 0;
}
