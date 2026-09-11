/* Stock-derived GPIO C. Names describe observed behavior; the original GD32
 * port source is unavailable. Vendor functions, clock helper and board API
 * are separately compiled by the isolated stock-address comparison tool. */
#include "gpio.h"

#if defined(GD_GPIO_CLOCK)
/* ITCM 0x3080: packed RCU offset/bit IDs from RAM 0x2400219c. */
void gd_gpio_clock_enable(uint32_t port)
{
    uint32_t clock_id = gd_gpio_clock_ids[port];
    uint32_t mask = 1u << (clock_id & 31);
    volatile uint32_t *reg = (volatile uint32_t *)(0x58024400u + (clock_id >> 6));
    *reg = mask | *reg;
}
#else
/* ITCM 0x30a8: the three pseudo-pins return the raw motor stall byte.
 * All other pins, including zero, use the supplied GPIO input register. */
uint8_t gpio_in_read(struct gpio_in pin)
{
    switch (pin.pin) {
    case 0x93:
        return gd_motor_y.stall;
    case 0x9b:
        return gd_motor_z.stall;
    case 0x97:
        return gd_motor_x.stall;
    }
    return !!(pin.regs->input & pin.bit);
}

/* ITCM 0x37c8: mode packs the GPIO mode (0..3), AF (4..7), output
 * type (8), and speed selection (9). No pin or mode checks occur here. */
void gpio_peripheral(uint32_t pin, uint32_t mode, int32_t pullup)
{
    struct gd_gpio *gpio = gd_gpio_ports[pin >> 4];
    gd_gpio_clock_enable(pin >> 4);
    uint32_t pull = pullup ? (pullup > 0 ? 1 : 2) : 0;
    uint32_t bit = pin & 15;
    uint32_t shift = (pin & 7) * 4;
    volatile uint32_t *af = (volatile uint32_t *)((uintptr_t)gpio
                                                + (bit < 8 ? 0x20 : 0x24));
    *af = (*af & ~(15u << shift)) | (((mode >> 4) & 15) << shift);
    uint32_t mask = 3u << (bit * 2);
    gpio->mode = (gpio->mode & ~mask) | ((mode & 15) << (bit * 2));
    gpio->pull = (gpio->pull & ~mask) | (pull << (bit * 2));
    gpio->output_type = (gpio->output_type & ~(1u << bit))
        | (((mode >> 8) & 1) << bit);
    gpio->output_speed = (gpio->output_speed & ~mask)
        | ((mode & 0x200 ? 3u : 1u) << (bit * 2));
}
#endif
