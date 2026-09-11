#ifndef MAINBOARDGD_RECOVERED_STATE_H
#define MAINBOARDGD_RECOVERED_STATE_H

#include "gpio.h"
#include "mclib_state.h"

extern struct mclib_motor mclib_motor_x, mclib_motor_y, mclib_motor_z;
extern struct mclib_motor mclib_motor_extruder;

/* Matches the timer.c / Klipper timer ABI; callback pointer retains Thumb. */
struct timer {
    struct timer *next;
    uint_fast8_t (*func)(struct timer *);
    uint32_t waketime;
};
_Static_assert(sizeof(struct timer) == 12, "timer state size");
extern struct timer wrap_timer;
extern uint_fast8_t timer_wrap_event(struct timer *);
extern struct timer periodic_timer, sentinel_timer, deleted_timer;
extern struct timer *sched_timer_list, *sched_last_insert;
extern uint_fast8_t periodic_event(struct timer *);
extern uint_fast8_t sentinel_event(struct timer *);
extern uint_fast8_t deleted_event(struct timer *);
extern uint8_t next_sequence;

/* Two DMA destinations: two word-sized ADC samples per transfer. */
extern volatile uint32_t mclib_adc_dma_y[2], mclib_adc_dma_z[2];

/* RAM objects referred to by the initialized motor state. Their partial
 * layouts belong to mclib_state.h; this translation unit does not define storage. */
struct mclib_current_acquisition_state;
struct mclib_pwm_state;
extern struct mclib_current_acquisition_state mclib_acquisition_x;
extern struct mclib_current_acquisition_state mclib_acquisition_y;
extern struct mclib_current_acquisition_state mclib_acquisition_z;
extern struct mclib_current_acquisition_state mclib_acquisition_extruder;
extern struct mclib_pwm_state mclib_pwm_x, mclib_pwm_y, mclib_pwm_z;
extern struct mclib_pwm_state mclib_pwm_extruder;

/* Peripheral symbols resolve to MMIO, not initialized RAM allocations. */
extern struct gd_gpio gd_gpio_port_a, gd_gpio_port_b, gd_gpio_port_c;
extern struct gd_gpio gd_gpio_port_d, gd_gpio_port_e, gd_gpio_port_f;
extern struct gd_gpio gd_gpio_port_g, gd_gpio_port_h, gd_gpio_port_j;

#endif
