#ifndef __FF_FLASHFORGE_H
#define __FF_FLASHFORGE_H
// State shared between the FlashForge additions and stock Klipper files.
#include <stdint.h>
#include "autoconf.h" // CONFIG_FF_BOARD_EBOARD

extern uint32_t ff_shutdown_code;   // latched by shutdown_ec()
extern uint8_t ff_timer_close;      // call site of the last late timer
extern uint8_t ff_endstop_active;   // an endstop is being queried or homed

// The inductive sensor.  These live at fixed, scattered addresses in the
// stock image, so they are separate objects rather than one struct.
extern volatile uint32_t ff_eddy_value;      // 0x20000158 live reading
extern uint32_t ff_eddy_baseline;   // 0x20000144 reference it is compared to
extern uint32_t ff_eddy_offset;     // 0x2000019C added when re-baselining
extern volatile int32_t ff_eddy_peel;        // 0x200001A4 last peel measurement
extern int32_t ff_trigger_threshold;// 0x20000000 host-set trigger threshold
extern int16_t ff_eddy_threshold;   // 0x2000003E the value actually compared
extern uint32_t ff_pa_value;
extern uint8_t ff_eddy_armed, ff_eddy_calibrated;
// 0x2000003C: the virtual endstop level (1 = released, 0 = triggered).  It
// doubles as the "eddy detector is idle" flag that command_endstop_home sets
// when it disarms homing.
extern volatile uint8_t ff_eddy_pin_state;
extern uint32_t ff_eddy_dbg_baseline, ff_eddy_sample_ref;
extern struct timer ff_eddy_timer;
void ff_eddy_update(void);

void ff_eddy_rebaseline(void);
void ff_eddy_home_reset(void);
void ff_eddy_pin_init(void);
void ff_pa_action(uint32_t action, uint32_t pc);

#endif // ff_flashforge.h
