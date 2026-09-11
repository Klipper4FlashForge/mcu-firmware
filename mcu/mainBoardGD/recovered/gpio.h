#ifndef MAINBOARDGD_RECOVERED_GPIO_H
#define MAINBOARDGD_RECOVERED_GPIO_H

#include <stddef.h>
#include <stdint.h>
#include "gd32h7xx.h"

/* Register offsets are verified against ITCM 0x3010, 0x3158 and 0x3780.
 * GPIO ports use bases 0x58020000 + port * 0x400. */
struct gd_gpio {
    volatile uint32_t mode;
    volatile uint32_t output_type;
    volatile uint32_t output_speed;
    volatile uint32_t pull;
    volatile uint32_t input;
    volatile uint32_t output;
    volatile uint32_t set;
    volatile uint32_t lock;
    volatile uint32_t alternate[2];
    volatile uint32_t clear;
    volatile uint32_t toggle;
};
_Static_assert(offsetof(struct gd_gpio, input) == 0x10, "GPIO input offset");
_Static_assert(offsetof(struct gd_gpio, alternate) == 0x20, "GPIO AF offset");

struct gpio_in {
    uint8_t pin;
    struct gd_gpio *regs;
    uint32_t bit;
};
_Static_assert(sizeof(struct gpio_in) == 12, "GPIO input ABI");

struct gpio_out {
    uint8_t pin;
    struct gd_gpio *regs;
    uint32_t bit;
};
_Static_assert(sizeof(struct gpio_out) == 12, "GPIO output ABI");
struct gpio_in gpio_in_setup(uint32_t pin, int32_t pullup);
struct gpio_out gpio_out_setup(uint32_t pin, uint32_t value);
void gpio_out_reset(struct gpio_out pin, uint32_t value);
void gpio_out_toggle_noirq(struct gpio_out pin);
void gpio_out_write(struct gpio_out pin, uint32_t value);

/* The controller writes this status byte from the motor interrupt loop.
 * These are views of existing motor objects, not new allocations. */
struct gd_motor_gpio_state {
    uint8_t before_stall[0xd2];
    volatile uint8_t stall;
};
extern struct gd_motor_gpio_state gd_motor_x, gd_motor_y, gd_motor_z;
extern const uint32_t gd_gpio_clock_ids[];
extern struct gd_gpio *const gd_gpio_ports[];

void gd_gpio_clock_enable(uint32_t port);
uint8_t gpio_in_read(struct gpio_in pin);
void gpio_peripheral(uint32_t pin, uint32_t mode, int32_t pullup);

#endif
