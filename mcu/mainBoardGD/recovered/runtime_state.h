#ifndef MAINBOARDGD_RUNTIME_STATE_H
#define MAINBOARDGD_RUNTIME_STATE_H

#include <stdint.h>
#include "mclib_state.h"
#include "move_queue.h"
#include "serial.h"
#include "trsync.h"
#include "debug_scope.h"

/* Actual zero-initialized objects; unknown gaps are not declared as storage. */
extern uint32_t ff_close_num, ff_temp_waketime;
extern uint8_t gd_jscope_buffer[1024];
extern int8_t tasks_status;
extern uint8_t shutdown_status, shutdown_reason, ff_timer_close;
extern struct mclib_current_acquisition_state mclib_acquisition_extruder;
extern struct mclib_current_acquisition_state mclib_acquisition_y;
extern struct mclib_current_acquisition_state mclib_acquisition_x;
extern struct mclib_current_acquisition_state mclib_acquisition_z;
extern struct mclib_pwm_state mclib_pwm_extruder, mclib_pwm_y;
extern struct mclib_pwm_state mclib_pwm_x, mclib_pwm_z;

extern void *alloc_end;
extern struct task_wake analog_wake;
extern struct task_wake buttons_wake;
extern uint8_t command_sync_state, in_sendf;
extern uint32_t config_crc;
extern unsigned char dynamic_memory[0x5000];
extern uint16_t move_count;
extern struct move_node *move_free_list;
extern uint8_t move_item_size;
extern void *move_list;
struct oid_s;
extern struct oid_s *oids;
extern uint8_t oid_count;
extern uint32_t ff_pa_pc, ff_pa_action, ff_pa_value;

/* ATEPCS Arm32 jmp_buf reserves twenty 64-bit words, even though this image's
 * NOP-patched FP save/restore path only uses the integer context portion. */
extern uint64_t shutdown_jmp[20];
extern uint32_t stats_send_time, stats_send_time_high;
extern uint32_t stats_count, stats_sum, stats_sumsq;
extern uint32_t timer_repeat_until;
extern uint8_t gpio_step_inhibit_72, gpio_step_inhibit_73;

#endif
