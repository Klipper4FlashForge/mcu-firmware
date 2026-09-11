/* mainBoardGD motor state recovered from stock fb64911b.
 * Field names describe observed uses; opaque bytes are not recovered fields.
 * Layout is the 32-bit target ABI, not a portable host representation.
 */
#ifndef MAINBOARDGD_MCLIB_STATE_H
#define MAINBOARDGD_MCLIB_STATE_H

#include <stddef.h>
#include <stdint.h>
#include "gd32h7xx.h"

/* Integer first-order filter, init 0x08000b28 and update 0x08000b10.
 * The update divides the running sum by 2^shift using arithmetic shift.
 */
struct mclib_sample_filter {
    int32_t accumulator;
    uint16_t shift;
    uint8_t unknown_06[2];
};

/* Four objects at 0x24003750, 0x24003780, 0x240037b0, 0x240037e0.
 * Calibration update 0x3a18 samples signed low halfwords at register +0/+4,
 * filters them for 2000 calls, then copies the results into the offsets.
 */
struct mclib_current_acquisition_state {
    uint8_t polarity;
    uint8_t unknown_01[3];
    float measured_alpha;
    float measured_beta;
    union {
        uint32_t adc;                   /* SDK ADC peripheral address */
        uint8_t unknown_0c[4];
    };
    volatile uint32_t *sample_registers;
    /* IRQ calibration observes this shared status byte again at every return,
     * including after writing zero (ITCM 0x3a58); do not cache that load. */
    volatile uint8_t calibrating;
    uint8_t unknown_15;
    uint16_t calibration_samples;
    int16_t filtered_alpha;
    int16_t filtered_beta;
    int16_t offset_alpha;
    int16_t offset_beta;
    struct mclib_sample_filter alpha_filter;
    struct mclib_sample_filter beta_filter;
};

/* Four 12-byte objects starting at 0x24008840. The channel identifiers are
 * SDK encodings, not necessarily consecutive channel numbers.
 */
struct mclib_pwm_state {
    uint32_t timer;                      /* SDK peripheral address */
    union {
        uint32_t half_period_ticks;     /* 7500 at hardware init */
        uint8_t unknown_04[4];
    };
    uint8_t channels[4];
};

/* Produced by flash 0x08002e28 and consumed by ITCM 0x3b38. Primary and
 * extension are normalized timing fractions, not timer ticks. Polarity bits
 * 0/1 select the alpha/beta bridge write patterns. Exact electrical names
 * for these intervals remain provisional.
 */
struct mclib_pwm_pattern {
    uint8_t unknown_00[2];
    uint8_t polarity;
    uint8_t unknown_03;
    float alpha_primary;
    float alpha_extension;
    float alpha_remainder;
    float beta_primary;
    float beta_extension;
    float beta_remainder;
};

/* PI step 0x080020d0, reset 0x08002148. */
struct mclib_pi {
    float kp;
    float ki;
    uint8_t unknown_08[4];
    float integral_max;
    float integral_min;
    float output_max;
    float output_min;
    float integral;
    uint8_t unknown_20[4];
    float error;
    float output;
};

/* Observer state starts at motor +0xf0. The 0x08002c58 update equations
 * identify the estimated-current and low-pass EMF pairs; 0x08002d70 consumes
 * previous_angle when differentiating the observer angle.
 */
struct mclib_observer {
    float plant_a;                       /* 0x00 */
    float plant_b;                       /* 0x04 */
    union {
        struct {
            uint8_t unknown_008[4];
            float sliding_gain;         /* 0x0c: saturated correction */
            float error_limit;          /* 0x10 */
            float sliding_slope;        /* 0x14: linear correction gain */
            float emf_filter_gain;      /* 0x18 */
            float alpha_current_error;  /* 0x1c */
            float beta_current_error;   /* 0x20 */
        };
        uint8_t parameters_and_work_008[0x1c]; /* stock initializer alias */
    };
    float estimated_alpha_current;       /* 0x24 */
    float estimated_beta_current;        /* 0x28 */
    union {
        struct {
            float alpha_sliding_voltage; /* 0x2c */
            float beta_sliding_voltage;  /* 0x30 */
        };
        uint8_t work_02c[8];            /* retained opaque-view alias */
    };
    float filtered_alpha_emf;            /* 0x34 */
    float filtered_beta_emf;             /* 0x38 */
    float angle;                         /* 0x3c */
    float previous_angle;                /* 0x40 */
    float angle_compensation;           /* 0x44: observer phase correction */
    float angular_velocity;             /* 0x48 */
    float filtered_angular_velocity;    /* 0x4c */
    float scaled_velocity;              /* 0x50: filtered velocity * fixed scale */
};

struct mclib_motor {
    float resistance;                    /* 0x000 */
    float inductance;
    float motor_constant;
    uint8_t unknown_00c[4];
    float run_current;                   /* 0x010 */
    float hold_current;
    float hold_current_decrement;
    float active_current;
    float target_d_current;              /* 0x020 */
    float target_q_current;
    float measured_alpha_current;
    float measured_beta_current;
    float measured_d_current;            /* 0x030 */
    float measured_q_current;
    float alpha_voltage;
    float beta_voltage;
    float d_voltage;                     /* 0x040 */
    float q_voltage;
    uint8_t unknown_048[4];
    float electrical_angle;
    float observer_phase_error;          /* 0x050 */
    float filtered_observer_phase_error;
    uint8_t unknown_058[4];
    uint8_t direction;                   /* 0x05c */
    uint8_t unknown_05d[3];
    union {
        uint32_t step_position;          /* 0x060: wrapping directional count */
        uint32_t reset_work_060;         /* retained reset-source alias */
    };
    uint8_t unknown_064[4];
    uint16_t step_phase;                 /* 0x068 */
    uint16_t angle_increment;
    uint16_t interpolated_increment;
    uint16_t interpolated_phase;
    uint16_t microstep_exponent;         /* 0x070 */
    uint8_t interpolate;
    uint8_t unknown_073;
    uint32_t previous_step_time;
    uint32_t sampled_time;
    uint32_t elapsed_since_step;
    uint32_t step_interval;              /* 0x080 */
    union {
        uint32_t alternate_transition_interval; /* 0x084: hysteresis center */
        uint8_t unknown_084[4];         /* retained for stock byte initializers */
    };
    uint32_t stall_interval_limit;
    uint32_t idle_threshold;
    uint32_t hold_delay_ticks;           /* 0x090; time unit unresolved */
    uint32_t current_transition_ticks;   /* 0x094; time unit unresolved */
    uint8_t stall_gate_count;
    uint8_t unknown_099[3];
    float absolute_current_projection;
    float filtered_current_projection;  /* 0x0a0 */
    float stall_threshold;
    float resonance_amplitude[3];        /* 0x0a8: harmonics 1, 2, 4 */
    float resonance_phase1[3];           /* 0x0b4: direction != 0 */
    float resonance_phase2[3];           /* 0x0c0: direction == 0 */
    uint8_t mode;                        /* 0x0cc; transitions incomplete */
    uint8_t unknown_0cd;
    uint8_t raw_stall;
    uint8_t alternate_control_mode;
    uint8_t stall_timing_gate;           /* 0x0d0 */
    uint8_t idle_stall_gate;
    uint8_t stall_output;
    uint8_t unknown_0d3;
    struct mclib_pwm_pattern pwm_pattern; /* 0x0d4 */
    struct mclib_observer observer;      /* 0x0f0 */
    uint8_t unknown_144[0x140];
    struct mclib_pi d_current_pi;        /* 0x284 */
    struct mclib_pi q_current_pi;        /* 0x2b0 */
    struct mclib_pi auxiliary_pi;        /* 0x2dc */
    float angle_error;                   /* 0x308 */
    float speed_target;
    void *current_acquisition;           /* 0x310 */
    void *pwm_output;
};

struct mclib_oid {
    uint8_t stepper;
    uint8_t padding[3];
    struct mclib_motor *motor;
};

#define MCLIB_OFFSET(type, field, offset) \
    _Static_assert(offsetof(struct type, field) == (offset), #type "." #field)
_Static_assert(sizeof(float) == 4, "stock uses binary32 floats");
_Static_assert(sizeof(void *) == 4, "compile for the 32-bit target ABI");
_Static_assert(sizeof(struct mclib_sample_filter) == 8, "sample filter size");
_Static_assert(sizeof(struct mclib_current_acquisition_state) == 0x30,
               "current acquisition state size");
_Static_assert(sizeof(struct mclib_pwm_state) == 12, "PWM state size");
_Static_assert(sizeof(struct mclib_pwm_pattern) == 0x1c, "PWM pattern size");
MCLIB_OFFSET(mclib_pwm_pattern, polarity, 2);
MCLIB_OFFSET(mclib_pwm_pattern, alpha_primary, 4);
MCLIB_OFFSET(mclib_pwm_pattern, alpha_extension, 8);
MCLIB_OFFSET(mclib_pwm_pattern, alpha_remainder, 0xc);
MCLIB_OFFSET(mclib_pwm_pattern, beta_primary, 0x10);
MCLIB_OFFSET(mclib_pwm_pattern, beta_extension, 0x14);
MCLIB_OFFSET(mclib_pwm_pattern, beta_remainder, 0x18);
MCLIB_OFFSET(mclib_sample_filter, shift, 4);
MCLIB_OFFSET(mclib_current_acquisition_state, sample_registers, 0x10);
MCLIB_OFFSET(mclib_current_acquisition_state, adc, 0x0c);
MCLIB_OFFSET(mclib_current_acquisition_state, measured_alpha, 4);
MCLIB_OFFSET(mclib_current_acquisition_state, measured_beta, 8);
MCLIB_OFFSET(mclib_current_acquisition_state, calibrating, 0x14);
MCLIB_OFFSET(mclib_current_acquisition_state, calibration_samples, 0x16);
MCLIB_OFFSET(mclib_current_acquisition_state, offset_alpha, 0x1c);
MCLIB_OFFSET(mclib_current_acquisition_state, offset_beta, 0x1e);
MCLIB_OFFSET(mclib_current_acquisition_state, alpha_filter, 0x20);
MCLIB_OFFSET(mclib_current_acquisition_state, beta_filter, 0x28);
MCLIB_OFFSET(mclib_pwm_state, channels, 8);
MCLIB_OFFSET(mclib_pwm_state, half_period_ticks, 4);
_Static_assert(sizeof(struct mclib_pi) == 0x2c, "PI state size");
_Static_assert(sizeof(struct mclib_observer) == 0x54, "observer state size");
_Static_assert(sizeof(struct mclib_motor) == 0x318, "motor state size");
_Static_assert(sizeof(struct mclib_oid) == 8, "OID binding size");
MCLIB_OFFSET(mclib_oid, motor, 4);
MCLIB_OFFSET(mclib_pi, integral, 0x1c);
MCLIB_OFFSET(mclib_pi, error, 0x24);
MCLIB_OFFSET(mclib_pi, output, 0x28);
MCLIB_OFFSET(mclib_observer, plant_a, 0x00);
MCLIB_OFFSET(mclib_observer, plant_b, 0x04);
MCLIB_OFFSET(mclib_observer, sliding_gain, 0x0c);
MCLIB_OFFSET(mclib_observer, error_limit, 0x10);
MCLIB_OFFSET(mclib_observer, sliding_slope, 0x14);
MCLIB_OFFSET(mclib_observer, emf_filter_gain, 0x18);
MCLIB_OFFSET(mclib_observer, alpha_current_error, 0x1c);
MCLIB_OFFSET(mclib_observer, beta_current_error, 0x20);
MCLIB_OFFSET(mclib_observer, alpha_sliding_voltage, 0x2c);
MCLIB_OFFSET(mclib_observer, beta_sliding_voltage, 0x30);
MCLIB_OFFSET(mclib_observer, estimated_alpha_current, 0x24);
MCLIB_OFFSET(mclib_observer, estimated_beta_current, 0x28);
MCLIB_OFFSET(mclib_observer, filtered_alpha_emf, 0x34);
MCLIB_OFFSET(mclib_observer, filtered_beta_emf, 0x38);
MCLIB_OFFSET(mclib_observer, previous_angle, 0x40);
MCLIB_OFFSET(mclib_observer, angle_compensation, 0x44);
MCLIB_OFFSET(mclib_observer, angular_velocity, 0x48);
MCLIB_OFFSET(mclib_observer, filtered_angular_velocity, 0x4c);
MCLIB_OFFSET(mclib_observer, scaled_velocity, 0x50);
MCLIB_OFFSET(mclib_motor, resistance, 0x00);
MCLIB_OFFSET(mclib_motor, inductance, 0x04);
MCLIB_OFFSET(mclib_motor, motor_constant, 0x08);
MCLIB_OFFSET(mclib_motor, run_current, 0x10);
MCLIB_OFFSET(mclib_motor, hold_current, 0x14);
MCLIB_OFFSET(mclib_motor, hold_current_decrement, 0x18);
MCLIB_OFFSET(mclib_motor, active_current, 0x1c);
MCLIB_OFFSET(mclib_motor, direction, 0x5c);
MCLIB_OFFSET(mclib_motor, observer_phase_error, 0x50);
MCLIB_OFFSET(mclib_motor, filtered_observer_phase_error, 0x54);
MCLIB_OFFSET(mclib_motor, reset_work_060, 0x60);
MCLIB_OFFSET(mclib_motor, step_position, 0x60);
MCLIB_OFFSET(mclib_motor, step_phase, 0x68);
MCLIB_OFFSET(mclib_motor, angle_increment, 0x6a);
MCLIB_OFFSET(mclib_motor, microstep_exponent, 0x70);
MCLIB_OFFSET(mclib_motor, interpolate, 0x72);
MCLIB_OFFSET(mclib_motor, idle_threshold, 0x8c);
MCLIB_OFFSET(mclib_motor, alternate_transition_interval, 0x84);
MCLIB_OFFSET(mclib_motor, current_transition_ticks, 0x94);
MCLIB_OFFSET(mclib_motor, stall_threshold, 0xa4);
MCLIB_OFFSET(mclib_motor, resonance_amplitude, 0xa8);
MCLIB_OFFSET(mclib_motor, resonance_phase1, 0xb4);
MCLIB_OFFSET(mclib_motor, resonance_phase2, 0xc0);
MCLIB_OFFSET(mclib_motor, stall_output, 0xd2);
MCLIB_OFFSET(mclib_motor, pwm_pattern, 0xd4);
MCLIB_OFFSET(mclib_motor, observer, 0xf0);
MCLIB_OFFSET(mclib_motor, observer.plant_a, 0xf0);
MCLIB_OFFSET(mclib_motor, observer.plant_b, 0xf4);
MCLIB_OFFSET(mclib_motor, d_current_pi, 0x284);
MCLIB_OFFSET(mclib_motor, q_current_pi, 0x2b0);
MCLIB_OFFSET(mclib_motor, auxiliary_pi, 0x2dc);
MCLIB_OFFSET(mclib_motor, current_acquisition, 0x310);
MCLIB_OFFSET(mclib_motor, pwm_output, 0x314);
#undef MCLIB_OFFSET

/* Table at RAM 0x24002504, ordered X/Y/Z/extruder. Defined by the eventual
 * initialized-data recovery, with states at 0x2400282c / 0x24002514 /
 * 0x24002b44 / 0x240021ec. Do not duplicate these states per OID.
 */
extern struct mclib_motor *mclib_motors[4];
extern struct mclib_motor mclib_motor_x;
extern struct mclib_motor mclib_motor_y;
extern struct mclib_motor mclib_motor_z;
extern struct mclib_motor mclib_motor_extruder;

void mclib_init(void);
void mclib_control_loop_a(struct mclib_motor *motor);
void mclib_control_loop_b(struct mclib_motor *motor);
void mclib_gpio_direction(struct mclib_motor *motor, uint32_t value);
void mclib_gpio_disable(struct mclib_motor *motor);
void mclib_gpio_enable(struct mclib_motor *motor);
void mclib_gpio_step(struct mclib_motor *motor);
void mclib_timer_start(void);
void mclib_motor_reset(struct mclib_motor *motor);
void mclib_pwm_disable(void *pwm_output);
void mclib_pwm_update(struct mclib_pwm_state *pwm,
                      const struct mclib_pwm_pattern *pattern);
void mclib_pwm_prepare(struct mclib_pwm_pattern *pattern, float alpha, float beta);
void mclib_current_acquisition_reset(void *current_acquisition);
uint8_t mclib_current_acquisition_calibrate(void *current_acquisition);
void mclib_sample_filter_init(struct mclib_sample_filter *filter,
                             uint16_t shift, int16_t initial);
int16_t mclib_sample_filter_update(struct mclib_sample_filter *filter,
                                  int16_t sample);
void mclib_set_microstep(struct mclib_motor *motor, uint16_t exponent);
void mclib_set_run_current(struct mclib_motor *motor, float current);
void mclib_set_hold_current(struct mclib_motor *motor, float current);
float mclib_pi_step(struct mclib_pi *pi, float target, float measured);
void mclib_pi_reset(struct mclib_pi *pi);
void mclib_park(float alpha, float beta, float sine, float cosine,
               float *d_current, float *q_current);
void mclib_observer_reset(struct mclib_observer *observer);
void mclib_observer_update(struct mclib_observer *observer,
                           float alpha_voltage, float beta_voltage,
                           float alpha_current, float beta_current);
void mclib_inverse_park(float d, float q, float sine, float cosine,
                        float *alpha, float *beta);
void mclib_limit_dq_voltage(struct mclib_motor *motor);
float mclib_sqrt_positive(float value);

void command_config_mclib(uint32_t *args);
void command_mclib_config_microstep(uint32_t *args);
void command_mclib_config_stalldetect(uint32_t *args);
void command_mclib_set_current(uint32_t *args);
void command_mclib_set_pid_params(uint32_t *args);
void command_mclib_identify_motor(uint32_t *args);
void command_mclib_set_resonance_damp(uint32_t *args);

#endif
