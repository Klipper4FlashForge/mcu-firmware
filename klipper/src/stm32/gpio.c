// GPIO functions on stm32f4
//
// Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "board/irq.h" // irq_save
#include "command.h" // DECL_ENUMERATION_RANGE
#include "ff_flashforge.h" // ff_eddy_pin_state
#include "gpio.h" // gpio_out_setup
#include "internal.h" // gpio_peripheral
#include "n32g45x.h" // GPIO_Module
#include "sched.h" // sched_shutdown

DECL_ENUMERATION_RANGE("pin", "PA0", GPIO('A', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PB0", GPIO('B', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PC0", GPIO('C', 0), 16);
#ifdef GPIOD
DECL_ENUMERATION_RANGE("pin", "PD0", GPIO('D', 0), 16);
#endif
#ifdef GPIOE
DECL_ENUMERATION_RANGE("pin", "PE0", GPIO('E', 0), 16);
#endif
#ifdef GPIOF
DECL_ENUMERATION_RANGE("pin", "PF0", GPIO('F', 0), 16);
#endif
#ifdef GPIOG
DECL_ENUMERATION_RANGE("pin", "PG0", GPIO('G', 0), 16);
#endif
#ifdef GPIOH
DECL_ENUMERATION_RANGE("pin", "PH0", GPIO('H', 0), 16);
#endif
#ifdef GPIOI
DECL_ENUMERATION_RANGE("pin", "PI0", GPIO('I', 0), 16);
#endif

GPIO_Module * const digital_regs[] = {
    NS_GPIOA, NS_GPIOB, NS_GPIOC, NS_GPIOD,
};

// Position of the lowest set bit, 0..15 (0 when none is set)
static int
bit_to_pin(uint32_t bit)
{
    int pin;
    for (pin=0; pin<16; pin++)
        if (bit & (1 << pin))
            return pin;
    return 0;
}

// Convert a register and bit location back to an integer pin identifier.
// The port is found by walking digital_regs.
static int
regs_to_pin(GPIO_Module *regs, uint32_t bit)
{
    int i;
    for (i=0; i<ARRAY_SIZE(digital_regs); i++)
        if (digital_regs[i] == regs)
            return GPIO('A' + i, bit_to_pin(bit));
    return 0;
}

// Verify that a gpio is a valid pin
static int
gpio_valid(uint32_t pin)
{
    uint32_t port = GPIO2PORT(pin);
    return port < ARRAY_SIZE(digital_regs) && digital_regs[port];
}

struct gpio_out
gpio_out_setup(uint32_t pin, uint32_t val)
{
    if (!gpio_valid(pin))
        shutdown_ec(FF_EC_GPIO_NOT_AN_OUTPUT, "Not an output pin");
    GPIO_Module *regs = digital_regs[GPIO2PORT(pin)];
    gpio_clock_enable(regs);
    struct gpio_out g = { .regs=regs, .bit=GPIO2BIT(pin) };
    gpio_out_reset(g, val);
    return g;
}

void
gpio_out_reset(struct gpio_out g, uint32_t val)
{
    GPIO_Module *regs = g.regs;
    int pin = regs_to_pin(regs, g.bit);
    irqstatus_t flag = irq_save();
    regs->PBSC = val ? g.bit : g.bit << 16;
    gpio_peripheral(pin, GPIO_OUTPUT, 0);
    irq_restore(flag);
}

void
gpio_out_toggle_noirq(struct gpio_out g)
{
    GPIO_Module *regs = g.regs;
    regs->POD ^= g.bit;
}

void
gpio_out_toggle(struct gpio_out g)
{
    irqstatus_t flag = irq_save();
    gpio_out_toggle_noirq(g);
    irq_restore(flag);
}

void
gpio_out_write(struct gpio_out g, uint32_t val)
{
    GPIO_Module *regs = g.regs;
    if (val)
        regs->PBSC = g.bit;
    else
        regs->PBSC = g.bit << 16;
}


struct gpio_in
gpio_in_setup(uint32_t pin, int32_t pull_up)
{
    if (!gpio_valid(pin))
        shutdown_ec(FF_EC_GPIO_NOT_AN_INPUT, "Not a valid input pin");
    GPIO_Module *regs = digital_regs[GPIO2PORT(pin)];
    struct gpio_in g = { .regs=regs, .bit=GPIO2BIT(pin) };
    gpio_in_reset(g, pull_up);
    return g;
}

void
gpio_in_reset(struct gpio_in g, int32_t pull_up)
{
    GPIO_Module *regs = g.regs;
    int pin = regs_to_pin(regs, g.bit);
    irqstatus_t flag = irq_save();
    gpio_peripheral(pin, GPIO_INPUT, pull_up);
    irq_restore(flag);
}

// PD0 is the bed probe.  It has no port pin of its own: reads of it
// return the eddy detector's virtual endstop level instead.
#define FF_EDDY_ENDSTOP_PORT NS_GPIOD
#define FF_EDDY_ENDSTOP_BIT  (1 << 0)

uint8_t
gpio_in_read(struct gpio_in g)
{
    GPIO_Module *regs = g.regs;
    if (regs != FF_EDDY_ENDSTOP_PORT || g.bit != FF_EDDY_ENDSTOP_BIT)
        return !!(regs->PID & g.bit);
    return ff_eddy_pin_state;
}
