/* Button debouncing and acknowledged reports, from Klipper buttons.c,
 * Copyright (C) 2018 Kevin O'Connor, GPLv3.
 * Eight report bytes are shared by the timer and task; preserve the IRQ
 * boundaries and byte-counter wrapping. GPIO inputs retain the 12-byte ABI.
 */
#include "buttons.h"
#include "generated/generated.h"

enum { BF_NO_RETRANSMIT = 0x80, BF_PENDING = 0xff, BF_ACKED = 0xfe };
extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);
extern void *oid_next(uint8_t *index, void *type);
extern void irq_disable(void), irq_enable(void);
extern void sched_add_timer(struct timer *, uint8_t source);
extern void sched_del_timer(struct timer *);
extern uint8_t sched_check_wake(struct task_wake *);
extern void sched_wake_task(struct task_wake *);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern void command_sendf(const struct command_encoder *, ...);

uint_fast8_t buttons_event(struct timer *timer)
{
    struct buttons *b = (struct buttons *)timer;
    uint8_t i, bit, status = 0;
    for (i = 0, bit = 1; i < b->button_count; i++, bit <<= 1) {
        uint8_t value = gpio_in_read(b->pins[i]);
        if (value)
            status |= bit;
    }
    uint8_t diff = status ^ b->pressed;
    if (diff) {
        uint8_t debounced = ~(status ^ b->last_pressed);
        if (diff & debounced) {
            b->pressed = (b->pressed & ~debounced) | (status & debounced);
            if (b->report_count < sizeof(b->reports)) {
                b->reports[b->report_count++] = b->pressed;
                sched_wake_task(&buttons_wake);
                b->retransmit_state = BF_PENDING;
            }
        }
    }
    b->last_pressed = status;
    uint8_t retransmit = b->retransmit_state;
    if (!(retransmit & BF_NO_RETRANSMIT)) {
        retransmit--;
        if (retransmit & BF_NO_RETRANSMIT)
            sched_wake_task(&buttons_wake);
        b->retransmit_state = retransmit;
    }
    b->time.waketime += b->rest_ticks;
    return 1;
}

void command_config_buttons(uint32_t *args)
{
    uint8_t count = args[1];
    if (count > 8)
        sched_shutdown(ctr_lookup_static_string("Max of 8 buttons"));
    struct buttons *b = oid_alloc(args[0], command_config_buttons,
                                 sizeof(*b) + sizeof(b->pins[0]) * count);
    b->button_count = count;
    b->time.func = buttons_event;
}

void command_buttons_add(uint32_t *args)
{
    struct buttons *b = oid_lookup(args[0], command_config_buttons);
    uint8_t pos = args[1];
    if (pos >= b->button_count)
        sched_shutdown(ctr_lookup_static_string("Set button past maximum button count"));
    /* Stock loads both decoded pin and pull fields with LDRB at 0xc40/42. */
    b->pins[pos] = gpio_in_setup((uint8_t)args[2], (uint8_t)args[3]);
}

void command_buttons_query(uint32_t *args)
{
    struct buttons *b = oid_lookup(args[0], command_config_buttons);
    sched_del_timer(&b->time);
    b->time.waketime = args[1];
    b->rest_ticks = args[2];
    b->pressed = b->last_pressed = args[4];
    /* Stock publishes the ACK/retransmit header at 0xcba, snapshots the
     * full retransmit argument at 0xcc0, then clears report_count at 0xcc2.
     * Keep those stages distinct; the stored count still truncates to byte. */
    b->ack_count = 0;
    b->retransmit_state = BF_ACKED;
    uint32_t retransmit = args[3];
    b->report_count = 0;
    b->retransmit_count = retransmit;
    if (b->retransmit_count >= BF_NO_RETRANSMIT)
        sched_shutdown(ctr_lookup_static_string("Invalid buttons retransmit count"));
    if (b->rest_ticks)
        sched_add_timer(&b->time, 48);
}

void command_buttons_ack(uint32_t *args)
{
    struct buttons *b = oid_lookup(args[0], command_config_buttons);
    uint8_t count = args[1];
    b->ack_count += count;
    irq_disable();
    if (count >= b->report_count) {
        b->report_count = 0;
        b->retransmit_state = BF_ACKED;
    } else {
        uint8_t pending = b->report_count - count, i;
        for (i = 0; i < pending; i++)
            b->reports[i] = b->reports[i + count];
        b->report_count = pending;
    }
    irq_enable();
}

void buttons_task(void)
{
    if (!sched_check_wake(&buttons_wake))
        return;
    uint8_t oid = -1;
    struct buttons *b;
    while ((b = oid_next(&oid, command_config_buttons))) {
        if (b->retransmit_state != BF_PENDING)
            continue;
        irq_disable();
        uint8_t count = b->report_count;
        if (!count) {
            irq_enable();
            continue;
        }
        b->retransmit_state = b->retransmit_count;
        irq_enable();
        command_sendf(ctr_lookup_encoder("buttons_state oid=%c ack_count=%c state=%*s"),
                      oid, b->ack_count, count, b->reports);
    }
}
