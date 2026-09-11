/* Queued digital outputs/software PWM, from Klipper gpiocmds.c (GPLv3),
 * Copyright (C) 2016-2020 Kevin O'Connor.
 * mainBoardGD adds the 5ms queue-command clock clamp at 0x1a88. The actual
 * enqueue routine at 0x1ac0 remains out of line; the entry TU keeps that call
 * boundary without function-local code-generation settings.
 */
#include "digital_out.h"
#include "generated/generated.h"

enum { DF_ON = 1, DF_TOGGLING = 2, DF_CHECK_END = 4, DF_DEFAULT_ON = 16,
       SF_DONE = 0, SF_RESCHEDULE = 1 };
extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);
extern void *oid_next(uint8_t *index, void *type);
extern void irq_disable(void), irq_enable(void);
extern void sched_add_timer(struct timer *, uint8_t source);
extern void sched_del_timer(struct timer *);
extern uint32_t timer_read_time(void), timer_from_us(uint32_t usecs);
extern uint8_t timer_is_before(uint32_t first, uint32_t second);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern const char generated_string_00006ad5[];

#ifdef GD_DIGITAL_QUEUE_ENTRY
void command_queue_digital_out(uint32_t *args)
{
    uint32_t oid = args[0], requested = args[1], on_duration = args[2];
    uint32_t time = timer_read_time() + timer_from_us(5000);
    if (!timer_is_before(requested, time))
        time = requested;
    uint32_t adjusted[3] = {oid, time, on_duration};
    command_queue_digital_out_impl(adjusted);
}
#else
uint_fast8_t digital_toggle_event(struct timer *timer)
{
    struct digital_out_s *d = (struct digital_out_s *)timer;
    gpio_out_toggle_noirq(d->pin);
    d->flags ^= DF_ON;
    uint32_t waketime = d->timer.waketime;
    if (d->flags & DF_ON)
        waketime += d->on_duration;
    else
        waketime += d->off_duration;
    if (d->flags & DF_CHECK_END && !timer_is_before(waketime, d->end_time)) {
        d->timer.func = digital_load_event;
        waketime = d->end_time;
    }
    d->timer.waketime = waketime;
    return SF_RESCHEDULE;
}

uint_fast8_t digital_load_event(struct timer *timer)
{
    struct digital_out_s *d = (struct digital_out_s *)timer;
    if (move_queue_empty(&d->mq))
        sched_shutdown(ctr_lookup_static_string("Missed scheduling of next digital out event"));
    struct digital_move *m = (struct digital_move *)move_queue_pop(&d->mq);
    uint32_t on_duration = m->on_duration;
    uint8_t flags = on_duration ? DF_ON : 0;
    gpio_out_write(d->pin, flags);
    move_free(m);

    uint32_t end_time = 0;
    if (!flags || on_duration >= d->cycle_time) {
        if (!on_duration != !(d->flags & DF_DEFAULT_ON) && d->max_duration) {
            end_time = d->timer.waketime + d->max_duration;
            flags |= DF_CHECK_END;
        }
    } else {
        flags |= DF_TOGGLING;
        if (d->max_duration) {
            end_time = d->timer.waketime + d->max_duration;
            flags |= DF_CHECK_END;
        }
    }
    if (!move_queue_empty(&d->mq)) {
        struct digital_move *next = (struct digital_move *)move_queue_first(&d->mq);
        uint32_t wake = next->waketime;
        if (flags & DF_CHECK_END && timer_is_before(end_time, wake))
            sched_shutdown(ctr_lookup_static_string(generated_string_00006ad5));
        end_time = wake;
        flags |= DF_CHECK_END;
    }
    d->end_time = end_time;
    d->flags = flags | (d->flags & DF_DEFAULT_ON);
    if (!(flags & DF_TOGGLING)) {
        if (!(flags & DF_CHECK_END))
            return SF_DONE;
        d->timer.waketime = end_time;
        return SF_RESCHEDULE;
    }
    uint32_t waketime = d->timer.waketime + on_duration;
    if (flags & DF_CHECK_END && !timer_is_before(waketime, end_time)) {
        d->timer.waketime = end_time;
        return SF_RESCHEDULE;
    }
    d->timer.func = digital_toggle_event;
    d->timer.waketime = waketime;
    d->on_duration = on_duration;
    d->off_duration = d->cycle_time - on_duration;
    return SF_RESCHEDULE;
}

void command_config_digital_out(uint32_t *args)
{
    struct gpio_out pin = gpio_out_setup((uint8_t)args[1], !!args[2]);
    struct digital_out_s *d = oid_alloc(args[0], command_config_digital_out, sizeof(*d));
    d->pin = pin;
    d->flags = (args[2] ? DF_ON : 0) | (args[3] ? DF_DEFAULT_ON : 0);
    d->max_duration = args[4];
    move_queue_setup(&d->mq, sizeof(struct digital_move));
}

void command_set_digital_out_pwm_cycle(uint32_t *args)
{
    struct digital_out_s *d = oid_lookup(args[0], command_config_digital_out);
    irq_disable();
    if (!move_queue_empty(&d->mq))
        sched_shutdown(ctr_lookup_static_string("Can not set soft pwm cycle ticks while updates pending"));
    d->cycle_time = args[1];
    irq_enable();
}

void command_queue_digital_out_impl(uint32_t *args)
{
    struct digital_out_s *d = oid_lookup(args[0], command_config_digital_out);
    struct digital_move *m = move_alloc();
    uint32_t time = m->waketime = args[1];
    m->on_duration = args[2];
    irq_disable();
    int first = move_queue_push(&m->node, &d->mq);
    if (!first) {
        irq_enable();
        return;
    }
    uint8_t flags = d->flags;
    if (flags & DF_CHECK_END && timer_is_before(d->end_time, time))
        sched_shutdown(ctr_lookup_static_string(generated_string_00006ad5));
    d->end_time = time;
    d->flags = flags | DF_CHECK_END;
    if (!(flags & DF_TOGGLING && timer_is_before(d->timer.waketime, time))) {
        sched_del_timer(&d->timer);
        d->timer.waketime = time;
        d->timer.func = digital_load_event;
        sched_add_timer(&d->timer, 15);
    }
    irq_enable();
}

void command_update_digital_out(uint32_t *args)
{
    struct digital_out_s *d = oid_lookup(args[0], command_config_digital_out);
    sched_del_timer(&d->timer);
    if (!move_queue_empty(&d->mq))
        sched_shutdown(ctr_lookup_static_string("update_digital_out not valid with active queue"));
    uint8_t value = args[1], flags = d->flags, on_flag = value ? DF_ON : 0;
    gpio_out_write(d->pin, on_flag);
    if (!value != !(flags & DF_DEFAULT_ON) && d->max_duration) {
        d->timer.waketime = d->end_time = timer_read_time() + d->max_duration;
        d->timer.func = digital_load_event;
        d->flags = (flags & DF_DEFAULT_ON) | on_flag | DF_CHECK_END;
        sched_add_timer(&d->timer, 14);
    } else {
        d->flags = (flags & DF_DEFAULT_ON) | on_flag;
    }
}

void digital_out_shutdown(void)
{
    uint8_t oid = -1;
    struct digital_out_s *d;
    while ((d = oid_next(&oid, command_config_digital_out))) {
        /* Stock passes the mask value 16, not a normalized boolean. This
         * matters to the full-word GPIO motor-direction handoff ABI. */
        gpio_out_write(d->pin, d->flags & DF_DEFAULT_ON);
        d->flags = d->flags & DF_DEFAULT_ON ? DF_ON | DF_DEFAULT_ON : 0;
        move_queue_clear(&d->mq);
    }
}

void command_set_digital_out(uint32_t *args)
{
    (void)gpio_out_setup((uint8_t)args[0], (uint8_t)args[1]);
}
#endif
