/* Synchronized trigger dispatch derived from Klipper trsync.c, GPLv3,
 * Copyright (C) 2016-2021 Kevin O'Connor.
 * mainBoardGD retains its 36-byte OID and linked-list callback layout.
 * Stock uses scheduler source IDs 28 (expiry) and 29 (periodic report),
 * and its shutdown ABI accepts the generated string ID without an EC arg.
 */
#include "trsync.h"
#include "generated/generated.h"

enum { TSF_CAN_TRIGGER = 1, TSF_REPORT = 4 };
extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);
extern void *oid_next(uint8_t *index, void *type);
extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags), irq_disable(void), irq_enable(void);
extern void sched_add_timer(struct timer *, uint8_t source);
extern void sched_del_timer(struct timer *);
extern void sched_wake_task(struct task_wake *);
extern uint8_t sched_check_wake(struct task_wake *);
extern uint32_t timer_read_time(void);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern void command_sendf(const struct command_encoder *, ...);
extern const char generated_string_00006c87[];

void trsync_do_trigger(struct trsync *ts, uint8_t reason)
{
    uint8_t flags = ts->flags;
    if (!(flags & TSF_CAN_TRIGGER))
        return;
    ts->trigger_reason = reason;
    ts->flags = (flags & ~TSF_CAN_TRIGGER) | TSF_REPORT;
    while (ts->signals) {
        struct trsync_signal *tss = ts->signals;
        /* Release callback-owned links as the observed separate word
         * accesses: unlink first, snapshot the callback, then clear each
         * member before calling it. The local volatile view preserves these
         * publications without changing the shared record's type or ABI.
         */
        volatile struct trsync_signal *released = tss;
        ts->signals = released->next;
        trsync_callback_t func = released->func;
        released->next = NULL;
        released->func = NULL;
        func(tss, reason);
    }
    sched_wake_task(&trsync_wake);
}

uint_fast8_t trsync_expire_event(struct timer *timer)
{
    struct trsync *ts = (struct trsync *)((uint8_t *)timer
                                        - offsetof(struct trsync, expire_time));
    trsync_do_trigger(ts, ts->expire_reason);
    return 0;
}

uint_fast8_t trsync_report_event(struct timer *timer)
{
    struct trsync *ts = (struct trsync *)timer;
    ts->flags |= TSF_REPORT;
    sched_wake_task(&trsync_wake);
    ts->report_time.waketime += ts->report_ticks;
    return 1;
}

void command_config_trsync(uint32_t *args)
{
    struct trsync *ts = oid_alloc(args[0], command_config_trsync, sizeof(*ts));
    ts->report_time.func = trsync_report_event;
    ts->expire_time.func = trsync_expire_event;
}

struct trsync *trsync_oid_lookup(uint8_t oid)
{
    return oid_lookup(oid, command_config_trsync);
}

void trsync_add_signal(struct trsync *ts, struct trsync_signal *tss,
                       trsync_callback_t func)
{
    uint32_t flags = irq_save();
    if (tss->func || !func)
        sched_shutdown(ctr_lookup_static_string("Can't add signal that is already active"));
    tss->func = func;
    tss->next = ts->signals;
    ts->signals = tss;
    irq_restore(flags);
}

static void trsync_clear(struct trsync *ts)
{
    sched_del_timer(&ts->report_time);
    sched_del_timer(&ts->expire_time);
    struct trsync_signal *tss = ts->signals;
    while (tss) {
        struct trsync_signal *next = tss->next;
        tss->func = NULL;
        tss->next = NULL;
        tss = next;
    }
    /* Stock clears exactly the seven bytes from signals through
     * expire_reason, not the trailing OID padding. Its two overlapping word
     * stores include an unaligned store at signals+3. Describe the field
     * span, leaving transfer selection and scheduling to the compiler.
     */
    __builtin_memset((uint8_t *)ts + offsetof(struct trsync, signals), 0,
                     offsetof(struct trsync, expire_reason)
                     + sizeof(ts->expire_reason) - offsetof(struct trsync, signals));
}

void command_trsync_start(uint32_t *args)
{
    struct trsync *ts = trsync_oid_lookup(args[0]);
    irq_disable();
    trsync_clear(ts);
    ts->flags = TSF_CAN_TRIGGER;
    ts->report_time.waketime = args[1];
    ts->report_ticks = args[2];
    if (ts->report_ticks)
        sched_add_timer(&ts->report_time, 29);
    ts->expire_reason = args[3];
    irq_enable();
}

void command_trsync_set_timeout(uint32_t *args)
{
    struct trsync *ts = trsync_oid_lookup(args[0]);
    irq_disable();
    uint8_t flags = ts->flags;
    if (flags & TSF_CAN_TRIGGER) {
        sched_del_timer(&ts->expire_time);
        ts->expire_time.waketime = args[1];
        sched_add_timer(&ts->expire_time, 28);
    }
    irq_enable();
}

static void trsync_report(uint8_t oid, uint8_t flags, uint8_t reason, uint32_t clock)
{
    command_sendf(ctr_lookup_encoder(generated_string_00006c87),
                  oid, !!(flags & TSF_CAN_TRIGGER), reason, clock);
}

void command_trsync_trigger(uint32_t *args)
{
    uint8_t oid = args[0];
    struct trsync *ts = trsync_oid_lookup(oid);
    irq_disable();
    trsync_do_trigger(ts, args[1]);
    sched_del_timer(&ts->report_time);
    sched_del_timer(&ts->expire_time);
    ts->flags = 0;
    uint8_t reason = ts->trigger_reason;
    irq_enable();
    trsync_report(oid, 0, reason, 0);
}

void trsync_task(void)
{
    if (!sched_check_wake(&trsync_wake))
        return;
    uint8_t oid = -1;
    struct trsync *ts;
    while ((ts = oid_next(&oid, command_config_trsync))) {
        if (!(ts->flags & TSF_REPORT))
            continue;
        uint32_t time = timer_read_time();
        irq_disable();
        uint8_t reason = ts->trigger_reason, flags = ts->flags;
        ts->flags = flags & ~TSF_REPORT;
        irq_enable();
        trsync_report(oid, flags, reason, time);
    }
}

void trsync_shutdown(void)
{
    uint8_t oid = -1;
    struct trsync *ts;
    while ((ts = oid_next(&oid, command_config_trsync)))
        trsync_clear(ts);
}
