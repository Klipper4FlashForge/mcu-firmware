/* Analog input scheduling from Klipper adccmds.c (GPLv3), Kevin O'Connor,
 * Copyright (C) 2016. GPIO ADC adaptation follows stock mainBoardGD's ADC2
 * polling, duplicate data-register reads, and per-channel cache writes.
 * There is no levelBoard analog_in_value debug-global store in this image.
 */
#include "analog_in.h"
#include "gd32h7xx.h"
#include "generated/generated.h"

extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);
extern void *oid_next(uint8_t *index, void *type);
extern void irq_disable(void), irq_enable(void);
extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags);
extern void sched_add_timer(struct timer *, uint8_t source);
extern void sched_del_timer(struct timer *);
extern uint8_t sched_check_wake(struct task_wake *);
extern void sched_wake_task(struct task_wake *);
extern void sched_try_shutdown(uint_fast8_t reason);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern void command_sendf(const struct command_encoder *, ...);
extern uint32_t timer_from_us(uint32_t usecs);
extern void gd_delay_us(uint32_t usecs);

#ifndef GD_ANALOG_GPIO_IMPLEMENTATION
uint_fast8_t analog_in_event(struct timer *timer)
{
    struct analog_in *a = (struct analog_in *)timer;
    uint32_t delay = gpio_adc_sample(a->pin);
    if (delay) {
        a->timer.waketime += delay;
        return 1;
    }
    uint16_t value = gpio_adc_read(a->pin);
    uint8_t state = a->state;
    if (state >= a->sample_count)
        state = 0;
    else
        value += a->value;
    a->value = value;
    a->state = state + 1;
    if (a->state < a->sample_count) {
        a->timer.waketime += a->sample_time;
        return 1;
    }
    if (__builtin_expect(a->value >= a->min_value && a->value <= a->max_value, 1)) {
        a->invalid_count = 0;
    } else {
        a->invalid_count++;
        if (a->invalid_count >= a->range_check_count) {
            sched_try_shutdown(ctr_lookup_static_string("ADC out of range"));
            a->invalid_count = 0;
        }
    }
    sched_wake_task(&analog_wake);
    a->next_begin_time += a->rest_time;
    a->timer.waketime = a->next_begin_time;
    return 1;
}

void command_config_analog_in(uint32_t *args)
{
    struct gpio_adc pin = gpio_adc_setup((uint8_t)args[1]);
    struct analog_in *a = oid_alloc(args[0], command_config_analog_in, sizeof(*a));
    a->timer.func = analog_in_event;
    a->pin = pin;
    a->state = 1;
}

void command_query_analog_in(uint32_t *args)
{
    struct analog_in *a = oid_lookup(args[0], command_config_analog_in);
    sched_del_timer(&a->timer);
    gpio_adc_cancel_sample(a->pin);
    a->next_begin_time = args[1];
    a->timer.waketime = a->next_begin_time;
    a->sample_time = args[2];
    a->sample_count = args[3];
    a->state = a->sample_count + 1;
    a->rest_time = args[4];
    a->min_value = args[5];
    a->max_value = args[6];
    a->range_check_count = args[7];
    if (a->sample_count)
        sched_add_timer(&a->timer, 31);
}

void analog_in_task(void)
{
    if (!sched_check_wake(&analog_wake))
        return;
    uint8_t oid = -1;
    struct analog_in *a;
    while ((a = oid_next(&oid, command_config_analog_in))) {
        if (a->state != a->sample_count)
            continue;
        irq_disable();
        if (a->state != a->sample_count) {
            irq_enable();
            continue;
        }
        uint16_t value = a->value;
        uint32_t next_begin_time = a->next_begin_time;
        a->state++;
        irq_enable();
        command_sendf(ctr_lookup_encoder("analog_in_state oid=%c next_clock=%u value=%hu"),
                      oid, next_begin_time, value);
    }
}

void analog_in_shutdown(void)
{
    uint8_t oid = -1;
    struct analog_in *a;
    while ((a = oid_next(&oid, command_config_analog_in))) {
        gpio_adc_cancel_sample(a->pin);
        if (a->sample_count) {
            a->state = a->sample_count + 1;
            a->next_begin_time += a->rest_time;
            a->timer.waketime = a->next_begin_time;
            sched_add_timer(&a->timer, 0);
        }
    }
}

/* The separate GPIO ADC translation unit retains the observed out-of-line
 * API boundaries instead of inlining MMIO into the scheduler callbacks. */
#else
#ifdef GD_ANALOG_DELAY
/* Stock 0x5ae0: initialize the DWT counter only when trace enable was clear,
 * then wait against the wrapping 600MHz count with a signed time comparison.
 * In particular, do not independently enable DWT if trace is already on. */
void gd_delay_us(uint32_t usecs)
{
    volatile uint32_t *demcr = (volatile uint32_t *)0xe000edfc;
    volatile uint32_t *dwt = (volatile uint32_t *)0xe0001000;
    if (!(*demcr & 0x1000000)) {
        *demcr |= 0x1000000;
        dwt[0] |= 1;
    }
    uint32_t end = dwt[1] + usecs * 600;
    while ((int32_t)(dwt[1] - end) < 0)
        ;
}
#else
void gpio_adc_cancel_sample(struct gpio_adc pin)
{
    uint32_t flags = irq_save();
    if ((pin.adc[0] & 0x10) && (pin.adc[0x44 / 4] & 31) == pin.channel) {
        pin.adc[0] = ~0x10u;
        if (pin.channel)
            gpio_adc_channel_samples[pin.channel] = pin.adc[0x64 / 4];
        (void)pin.adc[0x64 / 4];
    }
    irq_restore(flags);
}

uint16_t gpio_adc_read(struct gpio_adc pin)
{
    pin.adc[0] = ~0x10u;
    if (pin.channel)
        gpio_adc_channel_samples[pin.channel] = pin.adc[0x64 / 4];
    return pin.adc[0x64 / 4];
}

uint32_t gpio_adc_sample(struct gpio_adc pin)
{
    uint32_t status = pin.adc[0];
    if (!(status & 0x10)) {
        pin.adc[0x44 / 4] &= ~31u;
        pin.adc[0x44 / 4] |= pin.channel;
        pin.adc[2] |= 0x40000000;
    } else if ((status & 2) && (pin.adc[0x44 / 4] & 31) == pin.channel) {
        return 0;
    }
    return timer_from_us(20);
}

struct gpio_adc gpio_adc_setup(uint32_t pin)
{
    static const uint8_t adc_pins[21] = {
        34, 35, 89, 87, 85, 83, 90, 88, 86, 84, 32, 33,
        0, 0, 0, 0, 0, 0, 254, 0, 0
    };
    uint32_t channel;
    for (channel = 0; channel < sizeof(adc_pins); channel++)
        if (adc_pins[channel] == pin)
            break;
    if (channel == sizeof(adc_pins))
        sched_shutdown(ctr_lookup_static_string("Not a valid ADC pin"));
    volatile uint32_t *adc = (volatile uint32_t *)0x40012c00;
    if (!(*(volatile uint32_t *)0x58024444 & (1u << 10))) {
        rcu_periph_clock_enable(0x110a);
        adc_deinit(0x40012c00);
        adc_clock_config(0x40012c00, 0xc0000);
        adc_channel_length_config(0x40012c00, 1, 1);
        adc[0x44 / 4] = channel | 0x4b00;
        adc[2] = 0x800001;
        gd_delay_us(10);
        adc[2] = 9;
        while (adc[2] & 8)
            ;
        adc[2] = 5;
        while (adc[2] & 4)
            ;
    }
    if (pin == 254)
        adc[2] |= 0x800000;
    else
        gpio_peripheral(pin, 3, 0);
    return (struct gpio_adc){adc, channel};
}
#endif
#endif
