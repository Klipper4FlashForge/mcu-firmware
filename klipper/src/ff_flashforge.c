// FlashForge Creator 5 additions to the Klipper MCU firmware.
//
// Recovered from the stock board images shipped in control-1.2.9.  The four
// boards are built from one source tree with a board selector: a command is
// compiled everywhere but its body folds away on the boards that do not
// implement it, which is why levelBoard carries an empty get_emcu_pa_value
// while eBoard has the real one.
//
// The command handlers themselves live in basecmd.c -- that is where the
// stock message ids place them.  This file holds the shared state.
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "board/irq.h" // irq_disable
#include "command.h"   // sendf
#include "ff_flashforge.h"

// Latched by shutdown_ec() so the host can name the fault.
uint32_t ff_shutdown_code;

// The call site of the last timer scheduled in the past.
uint8_t ff_timer_close;

// Shared with endstop.c: see ff_flashforge.h.
uint8_t ff_endstop_active;

uint32_t ff_pa_value;

// The eBoard implementation (eBoard.hex 0x080115ec) reconfigures TIM4, TIM8
// and a DMA1 stream for the pressure-advance pickup.  Not reconstructed.
void
ff_pa_action(uint32_t action, uint32_t pc)
{
}
