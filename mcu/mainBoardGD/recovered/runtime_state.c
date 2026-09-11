/* Proven objects inside mainBoardGD's ZI region 0x24002e88..0x2400b340.
 * No blanket zero array is used to hide unrecovered state or stack storage.
 * Each symbol gets a separate real NOBITS section under -fdata-sections;
 * tools/check-gd-bss.py validates exact addresses, sizes and target ABI.
 */
#include "runtime_state.h"

/* Timer-too-close diagnostics: writes at ITCM 0x4100/0x410a/0x4116,
 * report reads at 0x42ea..0x42ee and 0x43c6..0x43ca. */
uint32_t ff_close_num;                    /* 0x24002e88 */
/* JScope's RTT up-buffer configuration passes this base with size 1024.
 * Its end is the separately proven scheduler tasks_status byte. */
uint8_t gd_jscope_buffer[1024];           /* 0x24002e8c */
uint32_t ff_temp_waketime;                /* 0x24003294 */
uint8_t ff_timer_close;                   /* 0x24008a98 */

/* Scheduler byte accesses at 0x4278/0x428a, 0x431e and 0x434a. */
int8_t tasks_status;                     /* 0x2400328c */
uint8_t shutdown_status;                 /* 0x24003290 */
uint8_t shutdown_reason;                 /* 0x24003292 */

/* RTT lazy initialization and descriptor bounds establish these adjacent
 * objects. The host-owned offsets retain the volatile ABI in debug_scope.h. */
struct gd_rtt_control_block gd_rtt_control; /* 0x24003298, 168 bytes */
uint8_t gd_rtt_down_buffer[16];             /* 0x24003340 */
uint8_t gd_rtt_up_buffer[1024];             /* 0x24003350 */

/* Four 0x30-byte acquisition objects and four 0x0c-byte PWM objects. Their
 * typed layouts/offset assertions are owned by mclib_state.h, not duplicated
 * here. State pointers, hardware setup at flash 0x08001e18..0x08001e60, and
 * calibration/PWM consumers establish these identities and object strides.
 */
struct mclib_current_acquisition_state mclib_acquisition_extruder; /* 0x24003750 */
struct mclib_current_acquisition_state mclib_acquisition_y;        /* 0x24003780 */
struct mclib_current_acquisition_state mclib_acquisition_x;        /* 0x240037b0 */
struct mclib_current_acquisition_state mclib_acquisition_z;        /* 0x240037e0 */
struct mclib_pwm_state mclib_pwm_extruder;  /* 0x24008840 */
struct mclib_pwm_state mclib_pwm_y;         /* 0x2400884c */
struct mclib_pwm_state mclib_pwm_x;         /* 0x24008858 */
struct mclib_pwm_state mclib_pwm_z;         /* 0x24008864 */

/* Allocation/OID consumers are recovered in base_commands.c/oid_commands.c.
 * dynmem_start 0x2d88 returns 0x2400381c; dynmem_end 0x2d78 returns
 * 0x2400881c. Their difference proves the heap array's 0x5000-byte extent.
 */
void *alloc_end;                         /* 0x24003810 */
/* Analog sampler callback wakes its report task through this byte. */
struct task_wake analog_wake;             /* 0x24003814 */
struct task_wake buttons_wake;            /* 0x24003815 */
uint32_t config_crc;                     /* 0x24003818 */
unsigned char dynamic_memory[0x5000] __attribute__((aligned(4))); /* 0x2400381c */
uint16_t move_count;                     /* 0x2400881e */
struct move_node *move_free_list;         /* 0x24008820 */
uint8_t move_item_size;                   /* 0x24008824 */
void *move_list;                         /* 0x24008828 */
uint8_t oid_count;                       /* 0x2400882c */
struct oid_s *oids;                      /* 0x24008830 */

/* Protocol flags: byte RMW in command_find_block 0x15a8 and command_sendf
 * 0x1ca8, with sendf_shutdown's byte clear at 0x4522. */
uint8_t command_sync_state;              /* 0x24003816 */
uint8_t in_sendf;                        /* 0x2400881c */

/* command_get_pa 0x17c0 and command_pa_action 0x1a08 use full words. */
uint32_t ff_pa_pc;                       /* 0x24008834 */
uint32_t ff_pa_action;                   /* 0x24008838 */
uint32_t ff_pa_value;                    /* 0x2400883c */

/* RX's bound is the 384-byte comparison in serial_rx_byte 0x4698; TX's
 * 96-byte capacity is checked in console_sendf at 0x208e. Source declarations
 * and consumers retain the 16-bit RX and 8-bit TX positions, not int arrays.
 */
uint8_t receive_buf[384];                /* 0x24008870 */
uint16_t receive_pos;                    /* 0x240089f0 */
uint8_t transmit_buf[96];                /* 0x24008ab4 */
uint8_t transmit_max;                    /* 0x24008b14 */
uint8_t transmit_pos;                    /* 0x24008b15 */

/* Wake byte read/cleared by trsync_task; set by timer and trigger paths. */
struct task_wake trsync_wake;             /* 0x24008b16 */
/* GPIO pseudo-pins 0x72/0x73 write boolean values at 0x3766/0x377a;
 * toggle reads them before dispatching a rising motor step at 0x3332/0x33b8.
 */
uint8_t gpio_step_inhibit_72;             /* 0x24008b38 */
uint8_t gpio_step_inhibit_73;             /* 0x24008b39 */

/* Arm Compiler include/setjmp.h's Arm32 ABI is __int64 jmp_buf[20]. That
 * 160-byte extent exactly reaches the next known object at 0x24008a98.
 * Do not shrink it to the 44 bytes touched by stock's integer save path at
 * flash 0x08000488..0x080004a2: the FP call sites are NOP-patched in stock.
 */
uint64_t shutdown_jmp[20] __attribute__((aligned(8))); /* 0x240089f8 */

/* Statistics update 0x46c8 and get_uptime 0x17f0 use these five words. */
uint32_t stats_send_time;                /* 0x24008a9c */
uint32_t stats_send_time_high;           /* 0x24008aa0 */
uint32_t stats_count;                    /* 0x24008aa4 */
uint32_t stats_sum;                      /* 0x24008aa8 */
uint32_t stats_sumsq;                    /* 0x24008aac */
/* SysTick dispatch and timer_task share this wrap-safe repeat deadline. */
uint32_t timer_repeat_until;             /* 0x24008ab0 */

_Static_assert(sizeof(void *) == 4, "32-bit pointer ABI");
_Static_assert(sizeof(struct mclib_current_acquisition_state) == 0x30, "acquisition stride");
_Static_assert(sizeof(struct mclib_pwm_state) == 0x0c, "PWM stride");
_Static_assert(sizeof(dynamic_memory) == 0x5000, "observed dynamic memory bounds");
_Static_assert(sizeof(shutdown_jmp) == 160, "Arm32 jmp_buf capacity");
