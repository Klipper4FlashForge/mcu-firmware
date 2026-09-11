/* mainBoardGD double-scheduled stepper path, derived from Klipper stepper.c
 * (Kevin O'Connor, GPLv3). Source groups retain the measured out-of-line call
 * boundaries at 0x47b0/0x47b8, 0x4850 and 0x4900 without local compiler flags.
 * GD_STEPPER_LOAD retains the loader's out-of-line call boundary. Its full
 * 96-byte candidate fits stock's 0x4850..0x48b0 slot, but register allocation
 * and state-field instruction scheduling still differ from stock.
 */
#include "stepper.h"
#include "generated/generated.h"

enum {
    SF_DONE = 0, SF_RESCHEDULE = 1,
    MF_DIR = 1,
    SF_LAST_DIR = 1, SF_NEXT_DIR = 2, SF_INVERT_STEP = 4,
    SF_NEED_RESET = 8, SF_SINGLE_SCHED = 16,
    POSITION_BIAS = 0x40000000,
};
extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);
extern void *oid_next(uint8_t *index, void *type);
extern void irq_disable(void), irq_enable(void);
extern void sched_add_timer(struct timer *, uint8_t source);
extern void sched_del_timer(struct timer *);
extern uint32_t timer_read_time(void), timer_from_us(uint32_t usecs);
extern uint8_t timer_is_before(uint32_t time1, uint32_t time2);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern void command_sendf(const struct command_encoder *, ...);

#if defined(GD_STEPPER_ENTRY)
uint_fast8_t stepper_event(struct timer *timer)
{
    return stepper_event_full(timer);
}

#elif defined(GD_STEPPER_LOAD)
uint_fast8_t stepper_load_next(struct stepper *s)
{
    if (move_queue_empty(&s->mq)) {
        s->count = 0;
        return SF_DONE;
    }
    struct stepper_move *m = (struct stepper_move *)move_queue_pop(&s->mq);
    s->add = m->add;
    uint32_t next_interval = m->interval + m->add;
    s->next_step_time += m->interval;
    s->time.waketime = s->next_step_time;
    s->count = (uint32_t)m->count * 2;
    /* Commit the following interval after loading the move count. These are
     * ordinary object fields; all state is committed before GPIO/free calls.
     * Keeping this separate avoids combining waketime/interval into STRD.
     */
    s->interval = next_interval;
    if (m->flags & MF_DIR) {
        s->position = -s->position + m->count;
        gpio_out_toggle_noirq(s->dir_pin);
    } else {
        s->position += m->count;
    }
    move_free(m);
    return SF_RESCHEDULE;
}

#elif defined(GD_STEPPER_STOP)
static uint32_t stepper_get_position(struct stepper *s)
{
    uint32_t position = s->position - s->count / 2;
    if (position & 0x80000000U)
        return -position;
    return position;
}

void stepper_stop(struct trsync_signal *signal, uint8_t reason)
{
    (void)reason;
    struct stepper *s = (struct stepper *)((uint8_t *)signal
                                         - offsetof(struct stepper, stop_signal));
    sched_del_timer(&s->time);
    s->next_step_time = s->time.waketime = 0;
    s->position = -stepper_get_position(s);
    s->count = 0;
    s->flags = (s->flags & (SF_INVERT_STEP | SF_SINGLE_SCHED)) | SF_NEED_RESET;
    gpio_out_write(s->dir_pin, 0);
    gpio_out_write(s->step_pin, s->flags & SF_INVERT_STEP);
    while (!move_queue_empty(&s->mq))
        move_free(move_queue_pop(&s->mq));
}

#else
static struct stepper *stepper_oid_lookup(uint8_t oid)
{
    return oid_lookup(oid, command_config_stepper);
}

uint_fast8_t stepper_event_full(struct timer *timer)
{
    struct stepper *s = (struct stepper *)timer;
    gpio_out_toggle_noirq(s->step_pin);
    uint32_t curtime = timer_read_time();
    uint32_t min_next_time = curtime + s->step_pulse_ticks;
    s->count--;
    /* These branch hints are present in upstream's double-scheduled path. */
    if (__builtin_expect(!!(s->count & 1), 1))
        goto reschedule_min;
    if (__builtin_expect(!!s->count, 1)) {
        s->next_step_time += s->interval;
        s->interval += s->add;
        if (__builtin_expect(!!timer_is_before(s->next_step_time, min_next_time), 0))
            goto reschedule_min;
        s->time.waketime = s->next_step_time;
        return SF_RESCHEDULE;
    }
    uint_fast8_t ret = stepper_load_next(s);
    if (ret == SF_DONE || !timer_is_before(s->time.waketime, min_next_time))
        return ret;
    int32_t diff = s->time.waketime - min_next_time;
    if (diff < -(int32_t)timer_from_us(1000))
        sched_shutdown(ctr_lookup_static_string("Stepper too far in past"));
reschedule_min:
    s->time.waketime = min_next_time;
    return SF_RESCHEDULE;
}

void command_config_stepper(uint32_t *args)
{
    struct stepper *s = oid_alloc(args[0], command_config_stepper, sizeof(*s));
    int32_t invert_step = args[3];
    s->flags = invert_step > 0 ? SF_INVERT_STEP : 0;
    /* Both pin arguments are byte loads in stock (0xf30 and 0xf44).
     * Keep the truncation here: the shared GPIO API accepts a full word. */
    s->step_pin = gpio_out_setup((uint8_t)args[1], s->flags & SF_INVERT_STEP);
    s->dir_pin = gpio_out_setup((uint8_t)args[2], 0);
    s->position = -(uint32_t)POSITION_BIAS;
    s->step_pulse_ticks = args[4];
    move_queue_setup(&s->mq, sizeof(struct stepper_move));
    /* Stock config at 0xf08 does not assign time.func. The scheduler's
     * inline-stepper path recognizes this zero callback and calls stepper_event. */
}

void command_queue_step(uint32_t *args)
{
    struct stepper *s = stepper_oid_lookup(args[0]);
    struct stepper_move *m = move_alloc();
    m->interval = args[1];
    m->count = args[2];
    if (!m->count)
        sched_shutdown(ctr_lookup_static_string("Invalid count parameter"));
    m->add = args[3];
    m->flags = 0;
    irq_disable();
    uint8_t flags = s->flags;
    if (!!(flags & SF_LAST_DIR) != !!(flags & SF_NEXT_DIR)) {
        flags ^= SF_LAST_DIR;
        m->flags |= MF_DIR;
    }
    if (s->count) {
        s->flags = flags;
        move_queue_push(&m->node, &s->mq);
    } else if (flags & SF_NEED_RESET) {
        move_free(m);
    } else {
        s->flags = flags;
        move_queue_push(&m->node, &s->mq);
        stepper_load_next(s);
        sched_add_timer(&s->time, 0x16);
    }
    irq_enable();
}

void command_set_next_step_dir(uint32_t *args)
{
    struct stepper *s = stepper_oid_lookup(args[0]);
    uint8_t nextdir = args[1] ? SF_NEXT_DIR : 0;
    irq_disable();
    s->flags = (s->flags & ~SF_NEXT_DIR) | nextdir;
    irq_enable();
}

void command_reset_step_clock(uint32_t *args)
{
    struct stepper *s = stepper_oid_lookup(args[0]);
    uint32_t waketime = args[1];
    irq_disable();
    if (s->count)
        sched_shutdown(ctr_lookup_static_string("Can't reset time when stepper active"));
    s->next_step_time = s->time.waketime = waketime;
    s->flags &= ~SF_NEED_RESET;
    irq_enable();
}

void command_stepper_get_position(uint32_t *args)
{
    uint8_t oid = args[0];
    struct stepper *s = stepper_oid_lookup(oid);
    irq_disable();
    uint32_t position = s->position - s->count / 2;
    if (position & 0x80000000U)
        position = -position;
    irq_enable();
    command_sendf(ctr_lookup_encoder("stepper_position oid=%c pos=%i"),
                  oid, position - POSITION_BIAS);
}

void command_stepper_stop_on_trigger(uint32_t *args)
{
    struct stepper *s = stepper_oid_lookup(args[0]);
    struct trsync *ts = trsync_oid_lookup(args[1]);
    trsync_add_signal(ts, &s->stop_signal, stepper_stop);
}

void stepper_shutdown(void)
{
    uint8_t oid = 0xff;
    struct stepper *s;
    while ((s = oid_next(&oid, command_config_stepper))) {
        move_queue_clear(&s->mq);
        stepper_stop(&s->stop_signal, 0);
    }
}
#endif
