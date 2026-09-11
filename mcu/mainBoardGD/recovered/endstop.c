/* Endstop sampling from Klipper endstop.c, GPLv3,
 * Copyright (C) 2016-2021 Kevin O'Connor.
 * Stock mainBoardGD has no levelBoard eddy-sampler hooks or recover command.
 * Its three-word GPIO input handle makes this OID 44 bytes. A first matching
 * poll immediately performs the first oversample; trigger_count wraps as a
 * byte, and a completed trigger returns SF_DONE without clearing the flags.
 */
#include "endstop.h"
#include "generated/generated.h"

enum { ESF_PIN_HIGH = 1, ESF_HOMING = 2, SF_DONE = 0, SF_RESCHEDULE = 1 };
extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);
extern void irq_disable(void), irq_enable(void);
extern void sched_add_timer(struct timer *, uint8_t source);
extern void sched_del_timer(struct timer *);
extern void command_sendf(const struct command_encoder *, ...);

uint_fast8_t endstop_event(struct timer *timer)
{
    struct endstop *e = (struct endstop *)timer;
    uint8_t value = gpio_in_read(e->pin);
    uint32_t nextwake = e->time.waketime + e->rest_time;
    if ((value ? ~e->flags : e->flags) & ESF_PIN_HIGH) {
        e->time.waketime = nextwake;
        return SF_RESCHEDULE;
    }
    e->nextwake = nextwake;
    e->time.func = endstop_oversample_event;
    return endstop_oversample_event(timer);
}

uint_fast8_t endstop_oversample_event(struct timer *timer)
{
    struct endstop *e = (struct endstop *)timer;
    uint8_t value = gpio_in_read(e->pin);
    if ((value ? ~e->flags : e->flags) & ESF_PIN_HIGH) {
        e->time.func = endstop_event;
        e->time.waketime = e->nextwake;
        e->trigger_count = e->sample_count;
        return SF_RESCHEDULE;
    }
    uint8_t count = e->trigger_count - 1;
    if (!count) {
        trsync_do_trigger(e->ts, e->trigger_reason);
        return SF_DONE;
    }
    e->trigger_count = count;
    e->time.waketime += e->sample_time;
    return SF_RESCHEDULE;
}

void command_config_endstop(uint32_t *args)
{
    struct endstop *e = oid_alloc(args[0], command_config_endstop, sizeof(*e));
    /* 0xe1e/0xe20 load only each decoded protocol argument's low byte;
     * gpio_in_setup itself accepts full-word pin/pull arguments. */
    e->pin = gpio_in_setup((uint8_t)args[1], (uint8_t)args[2]);
}

void command_endstop_home(uint32_t *args)
{
    struct endstop *e = oid_lookup(args[0], command_config_endstop);
    sched_del_timer(&e->time);
    e->time.waketime = args[1];
    e->sample_time = args[2];
    e->sample_count = args[3];
    if (!e->sample_count) {
        e->flags = 0;
        e->ts = NULL;
        return;
    }
    e->time.func = endstop_event;
    e->rest_time = args[4];
    e->trigger_count = e->sample_count;
    e->flags = ESF_HOMING | (args[5] ? ESF_PIN_HIGH : 0);
    e->ts = trsync_oid_lookup(args[6]);
    e->trigger_reason = args[7];
    sched_add_timer(&e->time, 1);
}

void command_endstop_query_state(uint32_t *args)
{
    uint8_t oid = args[0];
    struct endstop *e = oid_lookup(oid, command_config_endstop);
    irq_disable();
    uint32_t nextwake = e->nextwake;
    uint8_t flags = e->flags;
    irq_enable();
    command_sendf(ctr_lookup_encoder("endstop_state oid=%c homing=%c next_clock=%u pin_value=%c"),
                  oid, !!(flags & ESF_HOMING), nextwake, gpio_in_read(e->pin));
}
