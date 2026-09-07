#ifndef __FF_FLASHFORGE_H
#define __FF_FLASHFORGE_H
// State shared between the FlashForge additions and the Klipper core.
#include <stdbool.h>
#include <stdint.h>

struct task_wake;
struct timer;

extern uint32_t ff_shutdown_code;   // latched by shutdown_ec()

// Fault codes latched by shutdown_ec() and read back by the host.  The
// gaps are codes that have been retired; ids are never reused.
enum {
    FF_EC_TRSYNC_SIGNAL_ACTIVE       = 1,
    FF_EC_TMCUART_DATA_TOO_LARGE     = 2,
    FF_EC_GPIO_NOT_AN_OUTPUT         = 11,
    FF_EC_GPIO_NOT_AN_INPUT          = 12,
    FF_EC_STEPPER_TOO_FAR_PAST       = 14,
    FF_EC_STEPPER_BAD_COUNT          = 15,
    FF_EC_STEPPER_ACTIVE             = 16,
    FF_EC_CLEAR_WHEN_NOT_SHUTDOWN    = 22,
    FF_EC_PWM_MISSED_EVENT           = 23,
    FF_EC_PWM_MAX_DURATION           = 24,
    FF_EC_PWM_QUEUE_MAX_DURATION     = 25,
    FF_EC_NEOPIXEL_DATA_SIZE         = 26,
    FF_EC_NEOPIXEL_UPDATE            = 27,
    FF_EC_DIGITAL_MISSED_EVENT       = 29,
    FF_EC_DIGITAL_MAX_DURATION       = 30,
    FF_EC_SOFT_PWM_UPDATES_PENDING   = 31,
    FF_EC_DIGITAL_QUEUE_MAX_DURATION = 32,
    FF_EC_DIGITAL_ACTIVE_QUEUE       = 33,
    FF_EC_TOO_MANY_BUTTONS           = 37,
    FF_EC_BUTTON_OUT_OF_RANGE        = 38,
    FF_EC_BUTTON_RETRANSMIT_COUNT    = 39,
    FF_EC_ALLOC_CHUNK                = 40,
    FF_EC_ALLOC_CHUNKS               = 41,
    FF_EC_MOVE_QUEUE_OVERFLOW        = 42,
    FF_EC_MOVE_REQUEST_SIZE          = 43,
    FF_EC_ALREADY_FINALIZED          = 44,
    FF_EC_INVALID_OID_TYPE           = 45,
    FF_EC_CANNOT_ASSIGN_OID          = 46,
    FF_EC_OIDS_ALREADY_ALLOCATED     = 47,
    FF_EC_HOST_EMERGENCY_STOP        = 49,
};

extern uint8_t ff_timer_close;      // call site of the last late timer
extern uint8_t ff_endstop_active;   // an endstop is being queried or homed
extern uint16_t analog_in_value;    // latest analog sample, for debug

// The inductive sensor.
extern volatile uint32_t ff_eddy_value;      // live reading
extern uint32_t ff_eddy_baseline;   // reference it is compared to
extern uint32_t ff_eddy_offset;     // added when re-baselining
extern volatile int32_t ff_eddy_peel;        // last peel measurement
extern int32_t ff_trigger_threshold;// host-set trigger threshold
extern int16_t ff_eddy_threshold;   // the value actually compared
extern uint32_t ff_pa_value;
extern uint8_t ff_eddy_armed, ff_eddy_calibrated;
// The virtual endstop level (1 = released, 0 = triggered).  It doubles as
// the "eddy detector is idle" flag that command_endstop_home sets when it
// disarms homing.
extern volatile bool ff_eddy_pin_state;
extern uint32_t ff_eddy_dbg_baseline, ff_eddy_sample_ref;
extern struct timer ff_eddy_timer;
extern struct task_wake ff_eddy_wake;

// ff_eddy.c
void ff_eddy_pin_init(void);
void ff_eddy_counter_init(void);
void ff_eddy_dma_init(void);
void ff_eddy_update(void);
void ff_eddy_check_trigger(void);
void ff_eddy_rebaseline(void);
void ff_eddy_home_reset(void);

// sched.c
void ff_eddy_timer_init(void);

void ff_pa_action(uint32_t action, uint32_t pc);

#endif // ff_flashforge.h
