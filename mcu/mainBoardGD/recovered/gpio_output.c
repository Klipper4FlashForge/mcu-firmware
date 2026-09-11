/* MainBoardGD output API and its motor pseudo-pins, stock ITCM 0x30f0..0x377e.
 * All physical GPIO accesses occur even for pseudo-pins. Logical motor actions
 * follow those writes; do not replace these with a table-only virtual GPIO.
 */
#include "gpio.h"
#include "mclib_state.h"

extern struct mclib_motor mclib_motor_x, mclib_motor_y, mclib_motor_z;
extern struct mclib_motor mclib_motor_extruder;
extern uint8_t gpio_step_inhibit_72, gpio_step_inhibit_73;
void mclib_gpio_direction(struct mclib_motor *, uint32_t);
void mclib_gpio_step(struct mclib_motor *);
void mclib_gpio_disable(struct mclib_motor *);
void mclib_gpio_enable(struct mclib_motor *);
uint32_t irq_save(void);
void irq_restore(uint32_t);
uint8_t ctr_lookup_static_string(const char *);
__attribute__((noreturn, nothrow)) void sched_shutdown(uint8_t);

#if defined(GD_GPIO_INPUT_SETUP)
struct gpio_in gpio_in_setup(uint32_t pin, int32_t pullup)
{
    if (pin >= 160 || !gd_gpio_ports[pin / 16])
        sched_shutdown(ctr_lookup_static_string("Not a valid input pin"));
    struct gpio_in result;
    result.pin = pin;
    result.regs = gd_gpio_ports[pin / 16];
    result.bit = 1u << (pin % 16);
    uint32_t flags = irq_save();
    gpio_peripheral(pin, 0, (int8_t)pullup);
    irq_restore(flags);
    return result;
}
#elif defined(GD_GPIO_OUTPUT_SETUP)
struct gpio_out gpio_out_setup(uint32_t pin, uint32_t value)
{
    if (pin >= 160 || !gd_gpio_ports[pin / 16])
        sched_shutdown(ctr_lookup_static_string("Not an output pin"));
    struct gd_gpio *regs = gd_gpio_ports[pin / 16];
    gd_gpio_clock_enable(pin / 16);
    struct gpio_out result;
    result.pin = pin;
    result.regs = regs;
    result.bit = 1u << (pin % 16);
    gpio_out_reset(result, value);
    return result;
}
#elif defined(GD_GPIO_OUTPUT_RESET)
void gpio_out_reset(struct gpio_out pin, uint32_t value)
{
    uint32_t flags = irq_save();
    struct gd_gpio *regs = gd_gpio_ports[pin.pin / 16];
    gd_gpio_clock_enable(pin.pin / 16);
    uint32_t bit = pin.pin % 16;
    volatile uint32_t *af = (volatile uint32_t *)((uintptr_t)regs
                                                + (bit < 8 ? 0x20 : 0x24));
    *af &= ~(15u << ((bit % 8) * 4));
    uint32_t mask = 3u << (bit * 2), output = 1u << (bit * 2);
    regs->mode = (regs->mode & ~mask) | output;
    regs->pull &= ~mask;
    regs->output_type &= ~(1u << bit);
    regs->output_speed = (regs->output_speed & ~mask) | output;
    if (value)
        pin.regs->set = pin.bit;
    else
        pin.regs->clear = pin.bit;
    /* The by-value pin tag cannot change across a motor call, so these four
     * cases are exclusive. This complete 196-byte candidate fits the stock
     * 264-byte span, but does not reproduce its redundant post-call checks.
     */
    if (pin.pin == 0x91) mclib_gpio_direction(&mclib_motor_y, value);
    else if (pin.pin == 0x95) mclib_gpio_direction(&mclib_motor_x, value);
    else if (pin.pin == 0x99) mclib_gpio_direction(&mclib_motor_z, value);
    else if (pin.pin == 0x9d) mclib_gpio_direction(&mclib_motor_extruder, value);
    irq_restore(flags);
}
#elif defined(GD_GPIO_OUTPUT_TOGGLE)
void gpio_out_toggle_noirq(struct gpio_out pin)
{
    pin.regs->toggle = pin.bit;
    uint32_t high = !!(pin.regs->output & pin.bit);
    /* Keep both physical accesses and the short-circuit inhibit reads before
     * motor dispatch. Each tag group is exclusive; the two groups stay in
     * step-before-direction order. This fits in 112 bytes, not stock-exact.
     */
    if (!gpio_step_inhibit_72 && !gpio_step_inhibit_73 && high) {
        if (pin.pin == 0x90) mclib_gpio_step(&mclib_motor_y);
        else if (pin.pin == 0x94) mclib_gpio_step(&mclib_motor_x);
        else if (pin.pin == 0x98) mclib_gpio_step(&mclib_motor_z);
        else if (pin.pin == 0x9c) mclib_gpio_step(&mclib_motor_extruder);
    }
    if (pin.pin == 0x91) mclib_gpio_direction(&mclib_motor_y, high);
    else if (pin.pin == 0x95) mclib_gpio_direction(&mclib_motor_x, high);
    else if (pin.pin == 0x99) mclib_gpio_direction(&mclib_motor_z, high);
    else if (pin.pin == 0x9d) mclib_gpio_direction(&mclib_motor_extruder, high);
}
#else
void gpio_out_write(struct gpio_out pin, uint32_t value)
{
    if (value)
        pin.regs->set = pin.bit;
    else
        pin.regs->clear = pin.bit;
    /* Independent checks preserve the observed enable-before-direction order.
     * Active-high electrical enable signals disable the associated controller.
     */
    if (pin.pin == 0x92) {
        if (value) mclib_gpio_disable(&mclib_motor_y);
        else mclib_gpio_enable(&mclib_motor_y);
    }
    if (pin.pin == 0x96) {
        if (value) mclib_gpio_disable(&mclib_motor_x);
        else mclib_gpio_enable(&mclib_motor_x);
    }
    if (pin.pin == 0x9a) {
        if (value) mclib_gpio_disable(&mclib_motor_z);
        else mclib_gpio_enable(&mclib_motor_z);
    }
    if (pin.pin == 0x9e) {
        if (value) mclib_gpio_disable(&mclib_motor_extruder);
        else mclib_gpio_enable(&mclib_motor_extruder);
    }
    if (pin.pin == 0x91) mclib_gpio_direction(&mclib_motor_y, value);
    if (pin.pin == 0x95) mclib_gpio_direction(&mclib_motor_x, value);
    if (pin.pin == 0x99) mclib_gpio_direction(&mclib_motor_z, value);
    if (pin.pin == 0x9d) mclib_gpio_direction(&mclib_motor_extruder, value);
    if (pin.pin == 0x72) gpio_step_inhibit_72 = !!value;
    if (pin.pin == 0x73) gpio_step_inhibit_73 = !!value;
}
#endif
