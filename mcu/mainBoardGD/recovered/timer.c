/* Cortex-M7 SysTick/DWT timer support. Based on Klipper's armcm_timer.c
 * (Kevin O'Connor, GPLv3), with mainBoardGD's observed IRQ priority/tag.
 * The wrap timer's placement and initialized data are not yet linked here.
 */
#include <stdint.h>

struct timer {
    struct timer *next;
    uint_fast8_t (*func)(struct timer *);
    uint32_t waketime;
};
extern struct timer wrap_timer; /* RAM 0x24002e78 */
extern void sched_add_timer(struct timer *, uint8_t tag);
extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags);

uint_fast8_t timer_wrap_event(struct timer *t)
{
    t->waketime += 0xffffff;
    return 1;
}

void timer_reset(void)
{
    sched_add_timer(&wrap_timer, 1);
}

void timer_cnt_init(void)
{
    *(volatile uint32_t *)0xe000edfc |= 0x01000000; /* DEMCR.TRCENA */
    *(volatile uint32_t *)0xe0001000 |= 1; /* DWT.CTRL.CYCCNTENA */
    *(volatile uint32_t *)0xe0001004 = 0;
    timer_reset();
    uint32_t flags = irq_save();
    *(volatile uint8_t *)0xe000ed23 = 0x20; /* SysTick priority */
    *(volatile uint32_t *)0xe000e010 = 7; /* SysTick CTRL */
    *(volatile uint32_t *)0xe000e014 = 0; /* LOAD */
    *(volatile uint32_t *)0xe000e018 = 0; /* VAL */
    *(volatile uint32_t *)0xe000ed04 = 0x04000000; /* pend SysTick */
    irq_restore(flags);
}
