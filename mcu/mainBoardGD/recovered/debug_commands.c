/* mainBoardGD debug commands; Klipper debugcmds.c, Kevin O'Connor, GPLv3.
 * Each read/write width and IRQ exclusion interval follows the stock body.
 */
#include <stdint.h>
#include "generated/generated.h"
extern void *command_decode_ptr(uint32_t address);
extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags);
extern void command_sendf(const struct command_encoder *, ...);

void command_debug_nop(uint32_t *args) { (void)args; }

void command_debug_ping(uint32_t *args)
{
    uint8_t size = args[0];
    void *data = command_decode_ptr(args[1]);
    command_sendf(ctr_lookup_encoder("pong data=%*s"), size, data);
}

void command_debug_read(uint32_t *args)
{
    uint8_t order = args[0];
    void *ptr = command_decode_ptr(args[1]);
    uint32_t value, flags = irq_save();
    switch (order) {
    default: value = *(volatile uint8_t *)ptr; break;
    case 1: value = *(volatile uint16_t *)ptr; break;
    case 2: value = *(volatile uint32_t *)ptr; break;
    }
    irq_restore(flags);
    command_sendf(ctr_lookup_encoder("debug_result val=%u"), value);
}

void command_debug_write(uint32_t *args)
{
    uint8_t order = args[0];
    void *ptr = command_decode_ptr(args[1]);
    uint32_t value = args[2], flags = irq_save();
    switch (order) {
    default: *(volatile uint8_t *)ptr = value; break;
    case 1: *(volatile uint16_t *)ptr = value; break;
    case 2: *(volatile uint32_t *)ptr = value; break;
    }
    irq_restore(flags);
}
