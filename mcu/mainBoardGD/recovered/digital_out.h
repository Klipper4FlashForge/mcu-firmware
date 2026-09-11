#ifndef MAINBOARDGD_RECOVERED_DIGITAL_OUT_H
#define MAINBOARDGD_RECOVERED_DIGITAL_OUT_H

#include "state.h"
#include "move_queue.h"

struct digital_out_s {
    struct timer timer;
    uint32_t on_duration, off_duration, end_time;
    struct gpio_out pin;
    uint32_t max_duration, cycle_time;
    struct move_queue_head mq;
    uint8_t flags;
};
struct digital_move {
    struct move_node node;
    uint32_t waketime, on_duration;
};
_Static_assert(sizeof(struct digital_out_s) == 56, "digital output OID allocation");
_Static_assert(sizeof(struct digital_move) == 12, "digital move allocation");
_Static_assert(offsetof(struct digital_out_s, pin) == 24, "digital GPIO handle");
_Static_assert(offsetof(struct digital_out_s, mq) == 44, "digital move queue");
_Static_assert(offsetof(struct digital_out_s, flags) == 52, "digital output flags");

uint_fast8_t digital_load_event(struct timer *);
uint_fast8_t digital_toggle_event(struct timer *);
void command_config_digital_out(uint32_t *args);
void command_queue_digital_out(uint32_t *args);
void command_queue_digital_out_impl(uint32_t *args);
void command_set_digital_out(uint32_t *args);
void command_set_digital_out_pwm_cycle(uint32_t *args);
void command_update_digital_out(uint32_t *args);
void digital_out_shutdown(void);
#endif
