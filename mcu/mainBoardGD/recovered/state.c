/* mainBoardGD's initialized RAM state, before mclib_init updates defaults.
 * Recovered from the 11,912-byte scatter-decompressed region at 0x24000000.
 * All omitted fields/padding are zero and included in the full-object gate.
 * Hex floats preserve stock binary32 values without decimal-rounding guesses.
 * Unknown byte-array fields remain opaque; they are data, never code blobs.
 */
#include "state.h"

/* RAM 0x24000000/08: DMA sample buffers, NOT unused zeros or alignment.
 * Hardware init at flash 0x08001e18..0x08001e60 stores these addresses in
 * Y/Z acquisition.sample_registers; DMA setup at 0x08001e72/0x08001ee0
 * uses them as destinations, with transfer counts of two at 0x08001e80
 * and 0x08001ee8. Explicit .data keeps their zeros in the initialized
 * scatter region, as observed, instead of moving them to the later ZI area.
 */
volatile uint32_t mclib_adc_dma_y[2]
    __attribute__((section(".data.mclib_adc_dma_y"))) = {0, 0};
volatile uint32_t mclib_adc_dma_z[2]
    __attribute__((section(".data.mclib_adc_dma_z"))) = {0, 0};

/* RAM 0x24002188/8c: scheduler links. The corresponding Klipper SchedStatus
 * fields are read/written by dispatch at ITCM 0x4440 and timer deletion at
 * 0x41c0. Stock task/shutdown status bytes live separately in the ZI area.
 */
struct timer *sched_timer_list = &periodic_timer;
struct timer *sched_last_insert = &periodic_timer;

/* RAM 0x24002190: replacement for an active timer that gets deleted.
 * ITCM 0x41c8..0x41ea updates its next/waketime and timer_list; callback
 * 0x2848 simply returns SF_DONE. Matches Klipper sched.c's deleted_timer.
 */
struct timer deleted_timer = {.func = deleted_event};

/* RAM 0x2400219c. Port I has no backing GPIO entry; J uses clock bit 8. */
const uint32_t gd_gpio_clock_ids[10] = {
    0x0f00, 0x0f01, 0x0f02, 0x0f03, 0x0f04,
    0x0f05, 0x0f06, 0x0f07, 0, 0x0f08
};

/* RAM 0x240021c4. Preserve the null I slot rather than compacting ports. */
struct gd_gpio *const gd_gpio_ports[10] = {
    &gd_gpio_port_a, &gd_gpio_port_b, &gd_gpio_port_c, &gd_gpio_port_d,
    &gd_gpio_port_e, &gd_gpio_port_f, &gd_gpio_port_g, &gd_gpio_port_h,
    0, &gd_gpio_port_j
};

/* The unnamed word at motor +0x00c contains binary32 24.0. The observer's
 * still-opaque +0x008 area contains binary32 36.0, 0.5, 72.0, 0x1.a8ebdp-3
 * at observer offsets +0x00c/+0x010/+0x014/+0x018 respectively. */
#define MOTOR_UNKNOWN_00C {0x00, 0x00, 0xc0, 0x41}
#define OBSERVER_UNKNOWN_PARAMETERS { \
    [6] = 0x10, [7] = 0x42, [11] = 0x3f, \
    [14] = 0x90, [15] = 0x42, \
    [16] = 0xe8, [17] = 0x75, [18] = 0x54, [19] = 0x3e \
}

/* Identical d/q regulator limits in all four initial objects. */
#define CURRENT_PI(KP, KI) { \
    .kp = (KP), .ki = (KI), \
    .integral_max = 0x1.7fd70ap+4f, .integral_min = -0x1.7fd70ap+4f, \
    .output_max = 0x1.7fd70ap+4f, .output_min = -0x1.7fd70ap+4f \
}
#define XY_AUXILIARY_PI { \
    .kp = 0x1.47ae14p-8f, .ki = 0x1.a36e2ep-15f, \
    .integral_max = 1.0f, .integral_min = -1.0f, \
    .output_max = 1.0f, .output_min = -1.0f \
}

/* RAM 0x240021ec: extruder's static defaults differ from the three axes. */
struct mclib_motor mclib_motor_extruder = {
    .resistance = 0x1.acccccp+2f,
    .inductance = 0x1.4e3bcep-7f,
    .motor_constant = 0x1.758e22p-8f,
    .unknown_00c = MOTOR_UNKNOWN_00C,
    .unknown_084 = {0x9f, 0x24, 0, 0},
    .stall_interval_limit = 0x927c,
    .observer = {
        .plant_a = 0x1.ef2f30p-1f,
        .plant_b = 0x1.414140p-8f,
        .parameters_and_work_008 = OBSERVER_UNKNOWN_PARAMETERS,
    },
    .d_current_pi = CURRENT_PI(0x1.005aa0p+6f, 0x1.0d6c4ap+1f),
    .q_current_pi = CURRENT_PI(0x1.005aa0p+6f, 0x1.0d6c4ap+1f),
    .current_acquisition = &mclib_acquisition_extruder,
    .pwm_output = &mclib_pwm_extruder,
};

/* RAM 0x24002504: protocol enumeration order is X, Y, Z, extruder. */
struct mclib_motor *mclib_motors[4] = {
    &mclib_motor_x, &mclib_motor_y, &mclib_motor_z, &mclib_motor_extruder
};

#define XY_INITIAL_STATE(ACQUISITION, PWM) { \
    .resistance = 0x1.666666p+0f, \
    .inductance = 0x1.89374cp-9f, \
    .motor_constant = 0x1.47ae14p-8f, \
    .unknown_00c = MOTOR_UNKNOWN_00C, \
    .interpolate = 1, \
    .unknown_084 = {0x27, 0x09, 0, 0}, \
    .stall_interval_limit = 0x927c, \
    .hold_delay_ticks = 100000000, \
    .current_transition_ticks = 200000000, \
    .stall_threshold = 1.0f, \
    .observer = { \
        .plant_a = 0x1.f40da8p-1f, \
        .plant_b = 0x1.111110p-6f, \
        .parameters_and_work_008 = OBSERVER_UNKNOWN_PARAMETERS, \
    }, \
    .d_current_pi = CURRENT_PI(0x1.2d97cap+4f, 0x1.c260f6p-2f), \
    .q_current_pi = CURRENT_PI(0x1.2d97cap+4f, 0x1.c260f6p-2f), \
    .auxiliary_pi = XY_AUXILIARY_PI, \
    .current_acquisition = &(ACQUISITION), \
    .pwm_output = &(PWM), \
}

/* RAM 0x24002514 / 0x2400282c: Y and X differ only in their dependencies. */
struct mclib_motor mclib_motor_y = XY_INITIAL_STATE(mclib_acquisition_y, mclib_pwm_y);
struct mclib_motor mclib_motor_x = XY_INITIAL_STATE(mclib_acquisition_x, mclib_pwm_x);

/* RAM 0x24002b44. */
struct mclib_motor mclib_motor_z = {
    .resistance = 0x1.99999ap+0f,
    .inductance = 0x1.54c986p-9f,
    .motor_constant = 0x1.a6b50cp-8f,
    .unknown_00c = MOTOR_UNKNOWN_00C,
    .interpolate = 1,
    .unknown_084 = {0x27, 0x09, 0, 0},
    .stall_interval_limit = 0x927c,
    .hold_delay_ticks = 100000000,
    .current_transition_ticks = 200000000,
    .stall_threshold = 0x1.8cccccp+1f,
    .observer = {
        .plant_a = 0x1.f03f04p-1f,
        .plant_b = 0x1.3b13b0p-6f,
        .parameters_and_work_008 = OBSERVER_UNKNOWN_PARAMETERS,
    },
    .d_current_pi = CURRENT_PI(0x1.05616cp+4f, 0x1.015bfcp-1f),
    .q_current_pi = CURRENT_PI(0x1.05616cp+4f, 0x1.015bfcp-1f),
    .current_acquisition = &mclib_acquisition_z,
    .pwm_output = &mclib_pwm_z,
};

/* GPIO's partial views alias the actual motor objects; no duplicate states. */
extern struct gd_motor_gpio_state gd_motor_x __attribute__((alias("mclib_motor_x")));
extern struct gd_motor_gpio_state gd_motor_y __attribute__((alias("mclib_motor_y")));
extern struct gd_motor_gpio_state gd_motor_z __attribute__((alias("mclib_motor_z")));

/* RAM 0x24002e5c: Klipper MESSAGE_DEST initial sequence, read as a byte in
 * command_encode at ITCM 0x1310, checked/incremented at 0x1626..0x1636.
 * The three following zero alignment bytes are linker layout, not fields.
 */
uint8_t next_sequence = 0x10;

/* RAM 0x24002e60/6c. periodic_event at ITCM 0x4060 updates both deadlines;
 * sentinel_event at 0x4528 shuts down with "sentinel timer called". These
 * are the corresponding initialized timer objects from Klipper sched.c.
 */
struct timer periodic_timer = {.next = &sentinel_timer, .func = periodic_event};
struct timer sentinel_timer = {.func = sentinel_event, .waketime = 0x80000000};

/* RAM 0x24002e78: callback relocation is code, not an encoded data constant. */
struct timer wrap_timer = {
    .next = 0,
    .func = timer_wrap_event,
    .waketime = 0x00ffffff,
};
