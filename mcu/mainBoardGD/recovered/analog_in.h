#ifndef MAINBOARDGD_RECOVERED_ANALOG_IN_H
#define MAINBOARDGD_RECOVERED_ANALOG_IN_H
#include "trsync.h" /* common timer and task_wake layouts */

struct gpio_adc {
    volatile uint32_t *adc;
    uint32_t channel;
};
_Static_assert(sizeof(struct gpio_adc) == 8, "ADC handle uses two ARM words");
struct analog_in {
    struct timer timer;
    uint32_t rest_time, sample_time, next_begin_time;
    uint16_t value, min_value, max_value;
    struct gpio_adc pin;
    uint8_t invalid_count, range_check_count, state, sample_count;
};
_Static_assert(sizeof(struct analog_in) == 44, "analog input OID allocation");
_Static_assert(offsetof(struct analog_in, pin) == 32, "analog ADC handle");
_Static_assert(offsetof(struct analog_in, state) == 42, "analog sampling state");
extern struct task_wake analog_wake; /* 0x24003814, one byte */
/* 0x24008b18; allocation extent is NOT established. Stock channel18 stores
 * at base+36, beyond the separate known inhibit bytes at base+32/+33.
 * Do not silently invent a 21-element BSS object overlapping those globals. */
extern uint16_t gpio_adc_channel_samples[];

struct gpio_adc gpio_adc_setup(uint32_t pin);
uint32_t gpio_adc_sample(struct gpio_adc pin);
uint16_t gpio_adc_read(struct gpio_adc pin);
void gpio_adc_cancel_sample(struct gpio_adc pin);
uint_fast8_t analog_in_event(struct timer *);
void command_config_analog_in(uint32_t *args);
void command_query_analog_in(uint32_t *args);
void analog_in_task(void);
void analog_in_shutdown(void);
#endif
