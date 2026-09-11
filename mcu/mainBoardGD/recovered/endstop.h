#ifndef MAINBOARDGD_RECOVERED_ENDSTOP_H
#define MAINBOARDGD_RECOVERED_ENDSTOP_H

#include "trsync.h"

struct endstop {
    struct timer time;
    struct gpio_in pin;
    uint32_t rest_time, sample_time, nextwake;
    struct trsync *ts;
    uint8_t flags, sample_count, trigger_count, trigger_reason;
};
_Static_assert(sizeof(struct endstop) == 44, "endstop OID allocation");
_Static_assert(offsetof(struct endstop, pin) == 12, "endstop GPIO handle");
_Static_assert(offsetof(struct endstop, nextwake) == 32, "endstop next report clock");
_Static_assert(offsetof(struct endstop, flags) == 40, "endstop byte state");

uint_fast8_t endstop_event(struct timer *);
uint_fast8_t endstop_oversample_event(struct timer *);
void command_config_endstop(uint32_t *args);
void command_endstop_home(uint32_t *args);
void command_endstop_query_state(uint32_t *args);
#endif
