#ifndef MAINBOARDGD_RECOVERED_BUTTONS_H
#define MAINBOARDGD_RECOVERED_BUTTONS_H
#include "trsync.h"

struct buttons {
    struct timer time;
    uint32_t rest_ticks;
    uint8_t pressed, last_pressed;
    uint8_t report_count, reports[8];
    uint8_t ack_count, retransmit_state, retransmit_count, button_count;
    struct gpio_in pins[];
};
_Static_assert(sizeof(struct buttons) == 32, "buttons fixed OID prefix");
_Static_assert(offsetof(struct buttons, reports) == 19, "button report buffer");
_Static_assert(offsetof(struct buttons, pins) == 32, "button GPIO handle array");
extern struct task_wake buttons_wake; /* 0x24003815, one byte */

uint_fast8_t buttons_event(struct timer *);
void buttons_task(void);
void command_config_buttons(uint32_t *args);
void command_buttons_add(uint32_t *args);
void command_buttons_query(uint32_t *args);
void command_buttons_ack(uint32_t *args);
#endif
