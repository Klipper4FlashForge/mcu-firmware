#ifndef MAINBOARDGD_RECOVERED_STEPPER_H
#define MAINBOARDGD_RECOVERED_STEPPER_H
#include "state.h"
#include "move_queue.h"

/* Out handles have the same three-word calling layout as recovered inputs.
 * GPIO setup returns these via the AAPCS hidden result pointer; toggle/write
 * receive the three words in r0-r2, plus write's value in r3. */
/* Shared output definition and prototypes are in gpio.h via state.h. */

struct trsync_signal;
typedef void (*trsync_callback_t)(struct trsync_signal *, uint8_t);
struct trsync_signal {
    struct trsync_signal *next;
    trsync_callback_t func;
};
struct trsync;
struct trsync *trsync_oid_lookup(uint8_t oid);
void trsync_add_signal(struct trsync *, struct trsync_signal *, trsync_callback_t);

struct stepper_move {
    struct move_node node;
    uint32_t interval;
    int16_t add;
    uint16_t count;
    uint8_t flags;
};
struct stepper {
    struct timer time;
    uint32_t interval;
    int16_t add;
    uint32_t count, next_step_time, step_pulse_ticks;
    struct gpio_out step_pin, dir_pin;
    uint32_t position;
    struct move_queue_head mq;
    struct trsync_signal stop_signal;
    uint8_t flags : 8;
};
_Static_assert(sizeof(struct stepper_move) == 16, "stepper move allocation");
_Static_assert(offsetof(struct stepper_move, add) == 8, "move acceleration");
_Static_assert(offsetof(struct stepper_move, count) == 10, "move count");
_Static_assert(sizeof(struct stepper) == 0x50, "stepper allocation");
_Static_assert(offsetof(struct stepper, count) == 0x14, "stepper event count");
_Static_assert(offsetof(struct stepper, step_pin) == 0x20, "step pin handle");
_Static_assert(offsetof(struct stepper, dir_pin) == 0x2c, "direction handle");
_Static_assert(offsetof(struct stepper, mq) == 0x3c, "stepper queue");
_Static_assert(offsetof(struct stepper, stop_signal) == 0x44, "stepper trigger");

uint_fast8_t stepper_event(struct timer *timer);
uint_fast8_t stepper_event_full(struct timer *timer);
uint_fast8_t stepper_load_next(struct stepper *stepper);
void stepper_stop(struct trsync_signal *, uint8_t reason);
void stepper_shutdown(void);
void command_config_stepper(uint32_t *args);
void command_queue_step(uint32_t *args);
void command_reset_step_clock(uint32_t *args);
void command_set_next_step_dir(uint32_t *args);
void command_stepper_get_position(uint32_t *args);
void command_stepper_stop_on_trigger(uint32_t *args);
#endif
