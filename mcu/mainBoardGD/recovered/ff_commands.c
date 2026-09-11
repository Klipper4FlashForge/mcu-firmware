/* FlashForge command handlers recovered from mainBoardGD ITCM.
 * Addresses and pool extents are checked by tools/check-gd-core.py.
 * The unused param_value encoder is deliberately passed through: stock's
 * generated lookup returns NULL for it. Do not "repair" that behavior here.
 */
#include <stdint.h>
#include "generated/generated.h"

extern void command_sendf(const struct command_encoder *encoder, ...);
extern uint32_t ff_pa_value;       /* 0x2400883c */
extern uint32_t ff_pa_action;      /* 0x24008838 */
extern uint32_t ff_pa_pc;          /* 0x24008834 */
extern __attribute__((noreturn)) void gd_system_reset(void);

void command_get_basic_param(uint32_t *args)
{
    (void)args;
    command_sendf(ctr_lookup_encoder("param_value value=%u reserve=%u"), 0, 0);
}

void command_get_mcu_version(uint32_t *args)
{
    (void)args;
    command_sendf(ctr_lookup_encoder("mcu_version year=%u date=%u version=%u"),
                  2026, 627, 7092);
}

void command_get_pa(uint32_t *args)
{
    (void)args;
    const struct command_encoder *encoder = ctr_lookup_encoder("pa_value value=%u");
    command_sendf(encoder, ff_pa_value);
}

void command_pa_action(uint32_t *args)
{
    uint32_t action = args[0], pc = args[1];
    ff_pa_action = action;
    ff_pa_pc = pc;
}

void command_remove_peel(uint32_t *args)
{
    (void)args;
}

void command_reset(uint32_t *args)
{
    (void)args;
    gd_system_reset();
}
