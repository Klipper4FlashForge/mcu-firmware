/* Timer-list operations derived from Klipper sched.c (GPLv3).
 * All pointers are real typed scheduler state, not stock byte payloads.
 */
#include <stdint.h>
#include "state.h"

extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags);
extern uint8_t timer_is_before(uint32_t first, uint32_t second);
extern uint_fast8_t stepper_event(struct timer *timer);

void sched_del_timer(struct timer *del)
{
    uint32_t flags = irq_save();
    if (sched_timer_list == del) {
        deleted_timer.waketime = del->waketime;
        deleted_timer.next = del->next;
        sched_timer_list = &deleted_timer;
    } else {
        struct timer *pos;
        for (pos = sched_timer_list; pos->next; pos = pos->next) {
            if (pos->next == del) {
                pos->next = del->next;
                break;
            }
        }
    }
    if (sched_last_insert == del)
        sched_last_insert = &periodic_timer;
    irq_restore(flags);
}

unsigned int sched_timer_dispatch(void)
{
    struct timer *timer = sched_timer_list;
    uint_fast8_t result;
    if (__builtin_expect(!timer->func, 1))
        result = stepper_event(timer);
    else
        result = timer->func(timer);
    uint32_t waketime = timer->waketime;
    unsigned int next_waketime = waketime;
    if (__builtin_expect(result == 0, 0)) {
        next_waketime = timer->next->waketime;
        sched_timer_list = timer->next;
        if (sched_last_insert == timer)
            sched_last_insert = timer->next;
    } else if (!timer_is_before(waketime, timer->next->waketime)) {
        next_waketime = timer->next->waketime;
        sched_timer_list = timer->next;
        struct timer *pos = sched_last_insert;
        if (timer_is_before(waketime, pos->waketime))
            pos = sched_timer_list;
        struct timer *prev;
        for (;;) {
            prev = pos;
            pos = pos->next;
            if (timer_is_before(waketime, pos->waketime))
                break;
        }
        timer->next = pos;
        prev->next = timer;
        sched_last_insert = timer;
    }
    return next_waketime;
}
