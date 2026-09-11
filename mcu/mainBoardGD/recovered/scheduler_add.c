/* Timed callback insertion, derived from Klipper sched.c (GPLv3).
 * MainBoardGD retains FlashForge's timer-too-close diagnostics and tag byte.
 */
#include <stdint.h>
#include "state.h"
#include "generated/generated.h"

extern uint32_t irq_save(void), timer_read_time(void);
extern void irq_restore(uint32_t), timer_kick(void);
extern uint8_t timer_is_before(uint32_t, uint32_t);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern uint8_t shutdown_status, ff_timer_close;
extern uint32_t ff_close_num, ff_temp_waketime;

void sched_add_timer(struct timer *add, uint8_t tag)
{
    uint32_t waketime = add->waketime;
    uint32_t flags = irq_save();
    struct timer *head = sched_timer_list;
    if (__builtin_expect(timer_is_before(waketime, head->waketime), 0)) {
        uint32_t now = timer_read_time();
        if (timer_is_before(waketime, now)) {
            ff_temp_waketime = waketime;
            ff_close_num = now;
            ff_timer_close = tag;
            uint_fast8_t reason = ctr_lookup_static_string("Timer too close");
            if (!shutdown_status)
                sched_shutdown(reason);
        }
        if (head == &deleted_timer)
            add->next = deleted_timer.next;
        else
            add->next = head;
        deleted_timer.waketime = waketime;
        deleted_timer.next = add;
        sched_timer_list = &deleted_timer;
        timer_kick();
    } else {
        struct timer *previous;
        for (;;) {
            previous = head;
            head = head->next;
            if (timer_is_before(waketime, head->waketime))
                break;
        }
        add->next = head;
        previous->next = add;
    }
    irq_restore(flags);
}
