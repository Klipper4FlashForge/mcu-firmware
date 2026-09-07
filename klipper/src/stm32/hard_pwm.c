// Hardware PWM support on stm32
//
// Copyright (C) 2021  Michael Kurz <michi.kurz@gmail.com>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h" // CONFIG_MACH_STM32H7
#include "board/irq.h" // irq_save
#include "command.h" // shutdown
#include "gpio.h" // gpio_pwm_write
#include "sched.h" // sched_shutdown
#include "ctr.h" // DECL_CTR

#define MAX_PWM 255
DECL_CONSTANT("PWM_MAX", MAX_PWM);

// These diagnostics remain registered even though the levelBoard build uses
// the vendor's inert PWM entry points.
DECL_CTR("_DECL_STATIC_STR Not a valid PWM pin");
DECL_CTR("_DECL_STATIC_STR PWM already programmed at different speed");
DECL_CTR("_DECL_STATIC_STR Invalid PWM channel");

struct gpio_pwm
gpio_pwm_setup(uint8_t pin, uint32_t cycle_time, uint8_t val)
{
    return (struct gpio_pwm) { };
}

void
gpio_pwm_write(struct gpio_pwm g, uint32_t val)
{
}
