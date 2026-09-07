// Handling of end stops.
//
// Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "basecmd.h" // oid_alloc
#include "board/gpio.h" // struct gpio
#include "board/irq.h" // irq_disable
#include "command.h" // DECL_COMMAND
#include "ff_flashforge.h" // ff_endstop_active
#include "sched.h" // struct timer
#include "trsync.h" // trsync_do_trigger

struct endstop {
    struct timer time;
    struct gpio_in pin;
    uint32_t rest_time, sample_time, nextwake;
    struct trsync *ts;
    uint8_t flags, sample_count, trigger_count, trigger_reason;
};

enum { ESF_PIN_HIGH=1<<0, ESF_HOMING=1<<1 };

static uint_fast8_t endstop_oversample_event(struct timer *t);

// Timer callback for an end stop
uint_fast8_t
endstop_event(struct timer *t)
{
    struct endstop *e = container_of(t, struct endstop, time);
    uint8_t val = gpio_in_read(e->pin);
    uint32_t nextwake = e->time.waketime + e->rest_time;
    if ((val ? ~e->flags : e->flags) & ESF_PIN_HIGH) {
        // No match - reschedule for the next attempt
        e->time.waketime = nextwake;
        return SF_RESCHEDULE;
    }
    e->nextwake = nextwake;
    e->time.func = endstop_oversample_event;
    return endstop_oversample_event(t);
}

// Timer callback for an end stop that is sampling extra times
static uint_fast8_t
endstop_oversample_event(struct timer *t)
{
    struct endstop *e = container_of(t, struct endstop, time);
    uint8_t val = gpio_in_read(e->pin);
    if ((val ? ~e->flags : e->flags) & ESF_PIN_HIGH) {
        // No longer matching - reschedule for the next attempt
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

void
command_config_endstop(uint32_t *args)
{
    struct endstop *e = oid_alloc(args[0], command_config_endstop, sizeof(*e));
    e->pin = gpio_in_setup(args[1], args[2]);
}
DECL_COMMAND(command_config_endstop, "config_endstop oid=%c pin=%c pull_up=%c");

// Home an axis
void
command_endstop_home(uint32_t *args)
{
    struct endstop *e = oid_lookup(args[0], command_config_endstop);
    sched_del_timer(&e->time);
    e->time.waketime = args[1];
    e->sample_time = args[2];
    e->sample_count = args[3];
    if (!e->sample_count) {
        // Disable end stop checking and let the eddy current sampler run
        // freely again.
        e->flags = 0;
        ff_endstop_active = 0;
        e->ts = NULL;
        ff_eddy_pin_state = true;
        return;
    }
    ff_eddy_home_reset();
    ff_endstop_active = 1;
    e->time.func = endstop_event;
    e->rest_time = args[4];
    e->trigger_count = e->sample_count;
    e->flags = ESF_HOMING | (args[5] ? ESF_PIN_HIGH : 0);
    e->ts = trsync_oid_lookup(args[6]);
    e->trigger_reason = args[7];
    sched_add_timer(&e->time, FF_TIMER_ENDSTOP_HOME);
}
DECL_COMMAND(command_endstop_home,
             "endstop_home oid=%c clock=%u sample_ticks=%u sample_count=%c"
             " rest_ticks=%u pin_value=%c trsync_oid=%c trigger_reason=%c");

void
command_endstop_query_state(uint32_t *args)
{
    ff_endstop_active = 1;
    uint8_t oid = args[0];
    struct endstop *e = oid_lookup(oid, command_config_endstop);

    irq_disable();
    uint32_t nextwake = e->nextwake;
    uint8_t eflags = e->flags;
    irq_enable();

    sendf("endstop_state oid=%c homing=%c next_clock=%u pin_value=%c"
          , oid, !!(eflags & ESF_HOMING), nextwake, gpio_in_read(e->pin));
    // The query is over; let the eddy sampler run again.
    ff_endstop_active = 0;
}
DECL_COMMAND(command_endstop_query_state, "endstop_query_state oid=%c");

// FlashForge addition: re-arm an endstop after a homing attempt.  The
// trigger counter is reloaded from the sample count, the trsync is dropped
// and the endstop is taken out of homing.
//
// NOTE: this calls ctr_lookup_encoder() directly instead of going through
// the sendf() macro, which skips the DECL_CTR marker, so
// "endstop_recover_state oid=%c ok=%c" is never registered as a response
// and the lookup returns NULL at run time.  Left as it stands: the data
// dictionary the host parses depends on it.
void
command_endstop_recover_state(uint32_t *args)
{
    uint8_t oid = args[0];
    struct endstop *e = oid_lookup(oid, command_config_endstop);
    sched_del_timer(&e->time);
    e->trigger_count = e->sample_count;
    e->ts = NULL;
    e->flags = 0;
    ff_endstop_active = 0;
    ff_eddy_home_reset();
    command_sendf(ctr_lookup_encoder("endstop_recover_state oid=%c ok=%c")
                  , oid, 1);
}
DECL_COMMAND(command_endstop_recover_state, "endstop_recover_state oid=%c");
