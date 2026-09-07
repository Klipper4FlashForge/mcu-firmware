// FlashForge Creator 5 additions to the Klipper MCU firmware.
//
// All four boards are built from this one tree with a board selector: a
// command is compiled everywhere but its body folds away on the boards
// that do not implement it, so every board answers the same host protocol.
//
// The command handlers themselves live in basecmd.c, beside the rest of
// the message ids.  This file holds the state they share.
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "ff_flashforge.h" // ff_shutdown_code

// Latched by shutdown_ec() so the host can name the fault.
uint32_t ff_shutdown_code;

// The call site of the last timer scheduled in the past.
uint8_t ff_timer_close;

// Shared with endstop.c: see ff_flashforge.h.
uint8_t ff_endstop_active;

uint32_t ff_pa_value;

// Pressure advance drives the eBoard's extruder pickup through TIM4, TIM8
// and a DMA1 stream.  That body is not implemented in this tree.
void
ff_pa_action(uint32_t action, uint32_t pc)
{
}
