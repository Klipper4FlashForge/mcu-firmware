/* Source recovery with an isolated function-byte gate in tools/check-gd-motor.py.
 * This file is not a whole-image reconstruction.
 * Command handlers execute in ITCM; the public setters and math helpers execute
 * in flash. Stock linker veneers bridge the regions; they are not C functions.
 * Compile normally for the ITCM commands/initializer, with MCLIB_FLASH_HELPERS
 * for flash setters/math, with MCLIB_RESET_HELPER for flash motor reset,
 * with MCLIB_IO_HELPERS for the ITCM current/PWM interface, and with
 * MCLIB_REGISTER_HELPERS for the leaf timer/filter SDK routines.
 * MCLIB_CONTROL_LOOP_A/B build the complete X/Y and Z/extruder loop units.
 * MCLIB_GPIO_HOOKS builds the motor-side GPIO event handlers.
 * This keeps the observed translation-unit boundary
 * without suppressing inlining through function attributes. Registration and
 * section placement belong to the pending build integration.
 * See ../notes/motor-control.md for instruction-level evidence and limitations.
 */
#include "mclib_state.h"

#if defined(MCLIB_CONTROL_LOOP_A) || defined(MCLIB_CONTROL_LOOP_B)

/* Existing stock callees, not replacement stubs. Their definitions remain
 * explicit integration dependencies until their complete bodies are recovered.
 * Flash veneers 0x31ac / 0x31c0 enter ITCM 0x3a68 / 0x3a60 respectively.
 */
extern void mclib_current_acquisition_read(struct mclib_current_acquisition_state *state);
extern void mclib_current_acquisition_set_polarity(
    struct mclib_current_acquisition_state *state, uint8_t polarity);
extern void mclib_observer_update(struct mclib_observer *observer,
                                   float alpha_voltage, float beta_voltage,
                                   float alpha_current, float beta_current);
extern void mclib_sincos(float angle, float *sine, float *cosine);
extern void mclib_limit_dq_voltage(struct mclib_motor *motor);
extern void mclib_inverse_park(float d, float q, float sine, float cosine,
                              float *alpha, float *beta);
extern float mclib_sine(float angle);
extern float mclib_sqrt_positive(float value);

#if defined(MCLIB_CONTROL_LOOP_A)

/* Flash 0x08000c30, X/Y IRQ entry through ITCM veneer 0x5b1c. The full
 * 1352-byte extent ends at 0x08001178 and includes the embedded literal pool
 * at 0x0fe8..0x1000 as well as the trailing pool at 0x1164..0x1178.
 *
 * Unlike loop B, phase error does not depend on direction, and its lower
 * wrap comparison is ordered: NaN does not select the added 2*pi value.
 * The alternate controller enters/exits with +/-100 unsigned interval
 * hysteresis. No signed-shift or division guards are invented for its
 * unchecked speed estimate; C edge behavior remains target/compiler bound.
 * Separate products below retain stock's non-fused VMLA/VMLS arithmetic.
 * This complete source body still requires its full instruction/pool gate:
 * speculative arithmetic, FPSCR, store ordering and code layout may differ.
 * Common-profile candidate is 1284 bytes versus stock's 1352; it is not
 * byte-identical. Its unchecked speed estimate emits register LSL and UDIV,
 * and the separated products emit non-fused VMLA/VMLS as intended.
 */
void
mclib_control_loop_a(struct mclib_motor *motor)
{
    float phase_trig[2] = {0.0f, 0.0f};
    if (!motor->mode)
        return;

    uint32_t sampled = *(volatile uint32_t *)0x4000e024u;
    motor->sampled_time = sampled;
    uint32_t elapsed = sampled - motor->previous_step_time;
    motor->elapsed_since_step = elapsed;
    if (motor->step_interval > motor->stall_interval_limit
        || (int32_t)elapsed > (int32_t)motor->stall_interval_limit) {
        motor->stall_timing_gate = 1;
        motor->alternate_control_mode = 0;
        motor->stall_gate_count = 0;
    } else {
        motor->stall_timing_gate = 0;
    }

    mclib_current_acquisition_read(motor->current_acquisition);
    struct mclib_current_acquisition_state *acquisition = motor->current_acquisition;
    motor->measured_alpha_current = acquisition->measured_alpha;
    motor->measured_beta_current = acquisition->measured_beta;
    mclib_observer_update(&motor->observer, motor->alpha_voltage, motor->beta_voltage,
                          motor->measured_alpha_current, motor->measured_beta_current);

    float phase_error = (motor->electrical_angle - motor->observer.angle)
                        + 0x1.921fb8p+0f;
    if (phase_error > 0x1.921fb8p+1f)
        phase_error += -0x1.921fb8p+2f;
    if (-0x1.921fb8p+1f > phase_error)
        phase_error += 0x1.921fb8p+2f;
    motor->observer_phase_error = phase_error;
    float alpha_projection = motor->measured_alpha_current * motor->observer.filtered_beta_emf;
    float beta_projection = motor->measured_beta_current * motor->observer.filtered_alpha_emf;
    float projection = alpha_projection - beta_projection;
    float projection_delta = (projection - motor->filtered_current_projection) * 0.005f;
    float filtered_projection = motor->filtered_current_projection + projection_delta;
    float phase_delta = (phase_error - motor->filtered_observer_phase_error) * 0.005f;
    float filtered_phase = motor->filtered_observer_phase_error + phase_delta;
    motor->filtered_current_projection = filtered_projection;
    motor->absolute_current_projection = __builtin_fabsf(filtered_projection);
    motor->filtered_observer_phase_error = filtered_phase;
    motor->raw_stall = !(motor->absolute_current_projection >= motor->stall_threshold);

    uint8_t stall = 0;
    if (!motor->idle_stall_gate && !motor->stall_timing_gate
        && motor->stall_gate_count >= 17)
        stall = motor->raw_stall;
    motor->stall_output = stall;

    if (motor->mode == 2) {
        if (motor->step_interval < motor->alternate_transition_interval - 100u
            && !motor->alternate_control_mode) {
            motor->alternate_control_mode = 1;
            /* The entry call at 0x0d9a passes the retained phase-error value
             * in s0, not electrical_angle (Ghidra misses this argument).
             */
            mclib_sincos(phase_error, &phase_trig[0], &phase_trig[1]);
            float d_current = motor->measured_q_current * phase_trig[1];
            float q_current = motor->measured_q_current * phase_trig[0];
            float resistive_voltage = d_current * motor->resistance;
            float velocity_inductance = motor->observer.filtered_angular_velocity
                                        * motor->inductance;
            motor->target_d_current = d_current;
            motor->target_q_current = q_current;
            motor->auxiliary_pi.integral = d_current;
            float cross_voltage = q_current * velocity_inductance;
            motor->d_current_pi.integral = resistive_voltage - cross_voltage;
        }
        uint32_t interpolation_interval = motor->step_interval;
        if (interpolation_interval > motor->alternate_transition_interval + 100u)
            motor->alternate_control_mode = 0;
        elapsed = motor->elapsed_since_step;
        if ((int32_t)elapsed > (int32_t)motor->idle_threshold) {
            motor->idle_stall_gate = 1;
            motor->stall_gate_count = 0;
            motor->mode = 1;
        }
        if (motor->interpolate) {
            uint32_t increment = motor->angle_increment;
            uint32_t base_phase = motor->step_phase;
            uint8_t direction = motor->direction;
            float progress = (float)(int32_t)elapsed / (float)interpolation_interval;
            int32_t interpolated = (int32_t)(progress * (float)increment);
            motor->interpolated_increment = interpolated;
            uint32_t phase;
            if (direction) {
                phase = elapsed < interpolation_interval
                        ? base_phase + (uint32_t)interpolated
                        : base_phase + increment - 1u;
            } else {
                phase = elapsed < interpolation_interval
                        ? base_phase - (uint32_t)interpolated
                        : base_phase - increment + 1u;
            }
            motor->interpolated_phase = phase;
            motor->electrical_angle = (float)(uint16_t)phase * 0x1.921fb8p-14f;
        }
    }

    if (motor->mode == 1
        && (int32_t)motor->elapsed_since_step
           > (int32_t)(motor->idle_threshold + motor->hold_delay_ticks)) {
        motor->active_current -= motor->hold_current_decrement;
        if (!(motor->active_current >= motor->hold_current))
            motor->active_current = motor->hold_current;
    }

    float commanded_angle = motor->electrical_angle;
    float angle_error = commanded_angle - motor->observer.angle;
    uint32_t interval = motor->step_interval;
    uint32_t speed = 30000000u / (interval << motor->microstep_exponent);
    uint8_t direction = motor->direction;
    if (angle_error > 0x1.921fb8p+1f)
        angle_error += -0x1.921fb8p+2f;
    if (-0x1.921fb8p+1f > angle_error)
        angle_error += 0x1.921fb8p+2f;
    motor->angle_error = angle_error;
    motor->speed_target = (float)speed;
    if (!direction)
        motor->speed_target = -motor->speed_target;
    float speed_correction = angle_error * 10.0f;
    motor->speed_target = motor->speed_target + speed_correction;

    if (motor->alternate_control_mode == 1) {
        /* Stock passes scaled observer velocity as PI target (s0), and its
         * constructed speed_target as measured input (s1), in that order.
         */
        (void)mclib_pi_step(&motor->auxiliary_pi, motor->observer.scaled_velocity,
                            motor->speed_target);
        motor->target_d_current = motor->auxiliary_pi.output;
        mclib_sincos(motor->observer.angle, &phase_trig[0], &phase_trig[1]);
        mclib_park(motor->measured_alpha_current, motor->measured_beta_current,
                   phase_trig[0], phase_trig[1],
                   &motor->measured_d_current, &motor->measured_q_current);
        motor->d_voltage = mclib_pi_step(&motor->d_current_pi, motor->target_d_current,
                                         motor->measured_d_current);
        float d_squared = motor->d_voltage * motor->d_voltage;
        motor->q_voltage = mclib_sqrt_positive(0x1.1fc292p+9f - d_squared);
    } else {
        motor->target_d_current = 0.0f;
        motor->target_q_current = motor->active_current;
        if (interval >= 2468u) {
            const float *phases = direction ? motor->resonance_phase1 : motor->resonance_phase2;
            float harmonic = mclib_sine(commanded_angle + phases[0]);
            float compensation = harmonic * motor->resonance_amplitude[0];
            motor->target_d_current -= compensation;
            float twice_angle = motor->electrical_angle + motor->electrical_angle;
            harmonic = mclib_sine(twice_angle + phases[1]);
            compensation = harmonic * motor->resonance_amplitude[1];
            motor->target_d_current -= compensation;
            float fourth_angle = motor->electrical_angle * 4.0f;
            harmonic = mclib_sine(phases[2] + fourth_angle);
            compensation = harmonic * motor->resonance_amplitude[2];
            motor->target_d_current -= compensation;
        }
        mclib_sincos(motor->electrical_angle, &phase_trig[0], &phase_trig[1]);
        mclib_park(motor->measured_alpha_current, motor->measured_beta_current,
                   phase_trig[0], phase_trig[1],
                   &motor->measured_d_current, &motor->measured_q_current);
        motor->d_voltage = mclib_pi_step(&motor->d_current_pi, motor->target_d_current,
                                         motor->measured_d_current);
        motor->q_voltage = mclib_pi_step(&motor->q_current_pi, motor->target_q_current,
                                         motor->measured_q_current);
        mclib_limit_dq_voltage(motor);
    }
    mclib_inverse_park(motor->d_voltage, motor->q_voltage, phase_trig[0], phase_trig[1],
                       &motor->alpha_voltage, &motor->beta_voltage);
    if (motor->alpha_voltage > 23.99f)
        motor->alpha_voltage = 23.99f;
    if (motor->beta_voltage > 23.99f)
        motor->beta_voltage = 23.99f;
    if (!(motor->alpha_voltage >= -23.99f))
        motor->alpha_voltage = -23.99f;
    if (!(motor->beta_voltage >= -23.99f))
        motor->beta_voltage = -23.99f;
    mclib_pwm_prepare(&motor->pwm_pattern, motor->alpha_voltage * 0x1.555556p-5f,
                      motor->beta_voltage * 0x1.555556p-5f);
    mclib_pwm_update(motor->pwm_output, &motor->pwm_pattern);
    mclib_current_acquisition_set_polarity(motor->current_acquisition,
                                          motor->pwm_pattern.polarity);
}

#else /* MCLIB_CONTROL_LOOP_B */

/* Flash 0x08001258, reached by Z/extruder interrupts through ITCM 0x5b26.
 * The complete stock extent is 860 bytes: 814 bytes of instructions, a
 * two-byte alignment NOP, then eleven four-byte literals through 0x15b0.
 * This is the whole mode-gated execution body, not a loop excerpt.
 *
 * Timing differences are unsigned subtracts followed by the specifically
 * observed signed/unsigned comparisons. Interpolation still divides by the
 * unchecked interval, and its float-to-int conversion retains a full 32-bit
 * result until the final phase truncation. Invalid conversion inputs rely on
 * ARM VCVT behavior and are not a portable-C promise.
 *
 * Separate products below preserve non-fused VMLA/VMLS rounding. Lower float
 * clamps use !(x >= lower), because stock LT conditions also accept NaNs.
 * The common compiler's scheduling, speculation and register choices remain
 * subject to the full byte gate, including FPSCR/interrupt-visible behavior.
 * Selected accesses use a local volatile view to retain stock's snapshots,
 * separate publications and reloads without qualifying the shared layout.
 * Both directional subtractions execute before selection, as at 0x080012d6
 * and 0x080012da: even the unused result can affect cumulative FP exceptions.
 * The complete 860-byte code/pool extent now fits, with 104 matching bytes.
 * Ordered caller-state/FPSCR models pass; external callees remain explicitly
 * mocked there, so this is not complete control-loop or hardware equivalence.
 */
void
mclib_control_loop_b(struct mclib_motor *motor)
{
    volatile struct mclib_motor *state = motor;
    if (!state->mode)
        return;

    uint32_t sampled = *(volatile uint32_t *)0x4000e024u;
    uint32_t previous = state->previous_step_time;
    uint32_t recorded_interval = state->step_interval;
    state->sampled_time = sampled;
    uint32_t stall_limit = state->stall_interval_limit;
    uint32_t elapsed = sampled - previous;
    state->elapsed_since_step = elapsed;
    if (recorded_interval > stall_limit || (int32_t)elapsed > (int32_t)stall_limit) {
        state->stall_timing_gate = 1;
        state->stall_gate_count = 0;
    } else {
        state->stall_timing_gate = 0;
    }

    mclib_current_acquisition_read(motor->current_acquisition);
    struct mclib_current_acquisition_state *acquisition = motor->current_acquisition;
    motor->measured_alpha_current = acquisition->measured_alpha;
    motor->measured_beta_current = acquisition->measured_beta;
    mclib_observer_update(&motor->observer, motor->alpha_voltage, motor->beta_voltage,
                          motor->measured_alpha_current, motor->measured_beta_current);

    float commanded_angle = state->electrical_angle;
    float observed_angle = state->observer.angle;
    uint8_t direction = state->direction;
    /* Stock constants end in ...0fdc, one ULP beyond usual binary32 pi.
     * These are single conditional wrap steps, not repeated angle reduction.
     */
    float reverse_phase = observed_angle - commanded_angle;
    float forward_phase = commanded_angle - observed_angle;
    float phase_error = (direction ? forward_phase : reverse_phase) + 0x1.921fb8p+0f;
    *(volatile float *)&motor->observer_phase_error = phase_error;
    if (phase_error > 0x1.921fb8p+1f)
        *(volatile float *)&motor->observer_phase_error = phase_error + -0x1.921fb8p+2f;
    phase_error = *(volatile float *)&motor->observer_phase_error;
    if (!(phase_error >= -0x1.921fb8p+1f))
        *(volatile float *)&motor->observer_phase_error = phase_error + 0x1.921fb8p+2f;

    /* These observer fields are filtered EMF components, not sin/cos values. */
    float measured_alpha = state->measured_alpha_current;
    float alpha_emf = state->observer.filtered_alpha_emf;
    float beta_emf = state->observer.filtered_beta_emf;
    float previous_phase = state->filtered_observer_phase_error;
    float alpha_projection = measured_alpha * beta_emf;
    float measured_beta = state->measured_beta_current;
    float beta_projection = measured_beta * alpha_emf;
    float projection = alpha_projection - beta_projection;
    float previous_projection = state->filtered_current_projection;
    float projection_delta = (projection - previous_projection) * 0.005f;
    float filtered_projection = previous_projection + projection_delta;
    float phase_delta = (*(volatile float *)&motor->observer_phase_error
                        - previous_phase) * 0.005f;
    float filtered_phase = previous_phase + phase_delta;
    float stall_threshold = state->stall_threshold;
    state->filtered_current_projection = filtered_projection;
    float absolute_projection = __builtin_fabsf(filtered_projection);
    state->absolute_current_projection = absolute_projection;
    state->filtered_observer_phase_error = filtered_phase;
    state->raw_stall = !(absolute_projection >= stall_threshold);

    uint8_t stall = 0;
    if (!state->idle_stall_gate && !state->stall_timing_gate
        && state->stall_gate_count >= 17)
        stall = state->raw_stall;
    state->stall_output = stall;

    if (state->mode == 2) {
        elapsed = state->elapsed_since_step;
        if ((int32_t)elapsed > (int32_t)state->idle_threshold) {
            state->idle_stall_gate = 1;
            state->stall_gate_count = 0;
            state->mode = 1;
        }
        if (state->interpolate) {
            uint32_t interval = state->step_interval;
            uint32_t increment = state->angle_increment;
            uint32_t base_phase = state->step_phase;
            float progress = (float)(int32_t)elapsed / (float)interval;
            int32_t interpolated = (int32_t)(progress * (float)increment);
            state->interpolated_increment = interpolated;
            uint32_t phase;
            if (direction) {
                phase = elapsed < interval ? base_phase + (uint32_t)interpolated
                                           : base_phase + increment - 1u;
            } else {
                phase = elapsed < interval ? base_phase - (uint32_t)interpolated
                                           : base_phase - increment + 1u;
            }
            state->interpolated_phase = phase;
            state->electrical_angle = (float)(uint16_t)phase * 0x1.921fb8p-14f;
        }
    }

    if (state->mode == 1) {
        uint32_t idle_threshold = state->idle_threshold;
        uint32_t hold_delay = state->hold_delay_ticks;
        uint32_t idle_elapsed = state->elapsed_since_step;
        if ((int32_t)idle_elapsed > (int32_t)(idle_threshold + hold_delay)) {
            float decrement = state->hold_current_decrement;
            float current = state->active_current;
            float reduced_current = current - decrement;
            float hold = state->hold_current;
            state->active_current = reduced_current;
            if (!(reduced_current >= hold))
                state->active_current = hold;
        }
    }

    /* Stock reserves adjacent sine/cosine outputs and reloads both with VLDM. */
    float phase_trig[2];
    mclib_sincos(state->electrical_angle, &phase_trig[0], &phase_trig[1]);
    mclib_park(motor->measured_alpha_current, motor->measured_beta_current,
                phase_trig[0], phase_trig[1],
                &motor->measured_d_current, &motor->measured_q_current);
    state->target_d_current = 0.0f;
    state->target_q_current = state->active_current;
    motor->d_voltage = mclib_pi_step(&motor->d_current_pi, 0.0f, motor->measured_d_current);
    motor->q_voltage = mclib_pi_step(&motor->q_current_pi, motor->target_q_current,
                                    motor->measured_q_current);
    mclib_limit_dq_voltage(motor);
    mclib_inverse_park(motor->d_voltage, motor->q_voltage, phase_trig[0], phase_trig[1],
                       &motor->alpha_voltage, &motor->beta_voltage);

    volatile float *alpha = &motor->alpha_voltage;
    volatile float *beta = &motor->beta_voltage;
    if (*alpha > 23.99f)
        *alpha = 23.99f;
    if (*beta > 23.99f)
        *beta = 23.99f;
    if (!(*alpha >= -23.99f))
        *alpha = -23.99f;
    if (!(*beta >= -23.99f))
        *beta = -23.99f;

    float alpha_voltage = *alpha;
    float beta_voltage = *beta;
    mclib_pwm_prepare(&motor->pwm_pattern, alpha_voltage * 0x1.555556p-5f,
                      beta_voltage * 0x1.555556p-5f);
    mclib_pwm_update(motor->pwm_output, &motor->pwm_pattern);
    mclib_current_acquisition_set_polarity(motor->current_acquisition,
                                          motor->pwm_pattern.polarity);
}

#endif /* control-loop selection */

#elif defined(MCLIB_GPIO_HOOKS)

extern void mclib_sincos(float angle, float *sine, float *cosine);
extern void mclib_pwm_enable(void *pwm_output);

/* Flash 0x08000b78, six bytes. The GPIO dispatcher passes the entire value;
 * STRB retains its low byte, with no Boolean normalization.
 */
void
mclib_gpio_direction(struct mclib_motor *motor, uint32_t value)
{
    motor->direction = value;
}

/* Flash 0x08000b80..0x08000bb4. Does not reset PI state, acquisition state,
 * phase, or alternate_control_mode: these are not the general reset hook.
 * The interrupt-shared timing/idle gates are published as individual byte
 * stores at 0x08000baa/0x08000bae, not one merged halfword transaction.
 */
void
mclib_gpio_disable(struct mclib_motor *motor)
{
    motor->active_current = 0.0f;
    motor->target_d_current = 0.0f;
    motor->target_q_current = 0.0f;
    motor->step_position = 0;
    mclib_observer_reset(&motor->observer);
    mclib_pwm_disable(motor->pwm_output);
    motor->mode = 0;
    motor->raw_stall = 0;
    motor->stall_output = 0;
    *(volatile uint8_t *)&motor->stall_timing_gate = 1;
    *(volatile uint8_t *)&motor->idle_stall_gate = 0;
}

/* Flash 0x08000bb8..0x08000c30, including the angle literal at 0x0c2c.
 * Initial phase is 8192/65536 turn; stock uses pi rounded one ULP above the
 * usual binary32 pi. The unchecked shift is intentionally not guarded.
 */
void
mclib_gpio_enable(struct mclib_motor *motor)
{
    float sine, cosine;
    motor->previous_step_time = *(volatile uint32_t *)0x4000e024u;
    motor->step_phase = 8192;
    motor->electrical_angle = 0x1.921fb8p-1f;
    motor->angle_increment = 1u << (14 - motor->microstep_exponent);
    motor->active_current = motor->run_current;
    mclib_sincos(0x1.921fb8p-1f, &sine, &cosine);
    motor->target_d_current = motor->active_current * cosine;
    motor->target_q_current = motor->active_current * sine;
    mclib_pwm_enable(motor->pwm_output);
    motor->mode = 1;
}

/* Flash 0x08001670..0x0800170c, including both binary32 literals. Each call
 * records a step regardless of mode. Position and 16-bit electrical phase
 * wrap naturally; stall_gate_count saturates once per quarter turn. Only an
 * idle motor (mode 1) transitions to running (mode 2), restoring run current
 * and replacing the measured interval with idle_threshold for that step.
 * The interval publication at 0x08001684 precedes the position read at
 * 0x08001688. Local volatile views preserve that order and the phase reload
 * at 0x080016b2, also used for quarter-turn detection. The complete 156-byte
 * candidate retains initial register-encoding differences; the two
 * rounded FP multiplications remain separate.
 */
void
mclib_gpio_step(struct mclib_motor *motor)
{
    uint32_t sampled = *(volatile uint32_t *)0x4000e024u;
    uint8_t direction = motor->direction;
    uint32_t previous = motor->previous_step_time;
    motor->previous_step_time = sampled;
    *(volatile uint32_t *)&motor->step_interval = sampled - previous;
    uint32_t position = *(volatile uint32_t *)&motor->step_position;
    if (direction) {
        motor->step_position = position + 1;
        motor->step_phase += motor->angle_increment;
    } else {
        motor->step_position = position - 1;
        motor->step_phase -= motor->angle_increment;
    }
    uint16_t phase = *(volatile uint16_t *)&motor->step_phase;
    float phase_radians = (float)phase * 0x1.921fb8p+1f;
    motor->electrical_angle = phase_radians * 0x1p-15f;
    int can_count = motor->stall_gate_count != 255;
    if (!(phase & 0x3fffu) && can_count)
        motor->stall_gate_count++;
    if (motor->mode == 1) {
        motor->idle_stall_gate = 0;
        motor->active_current = motor->run_current;
        motor->step_interval = motor->idle_threshold;
        motor->mode = 2;
    }
}

#elif defined(MCLIB_REGISTER_HELPERS)

/* The SDK timer enable is in ITCM at 0x5120, reached here through flash
 * veneer 0x08003350. It performs a volatile read/OR/write of control bit 0.
 */

/* Flash 0x08002e18, called by registered mclib_init via ITCM veneer 0x5c16.
 * This starts the timer at 0x40000400 only after all four motors are reset
 * and their current/microstep defaults have been installed.
 */
void
mclib_timer_start(void)
{
    timer_enable(0x40000400u);
}

/* Flash 0x08000b10, called from ITCM through veneer 0x5bf8. Keep the full
 * signed quotient when subtracting from the accumulator: only the return
 * value is narrowed to signed 16 bits. Like filter init, signed overflow and
 * out-of-range shift inputs depend on the complete target byte gate, not a
 * portable interpretation of this unchecked fixed-point arithmetic.
 */
int16_t
mclib_sample_filter_update(struct mclib_sample_filter *filter, int16_t sample)
{
    int32_t sum = filter->accumulator + sample;
    int32_t output = sum >> filter->shift;
    filter->accumulator = sum - output;
    return output;
}

/* Flash 0x08000b28, reached from ITCM through veneer 0x5bee. This seeds the
 * running sum so the next equal sample leaves the filter output unchanged.
 * As with the stock microstep helper, unchecked signed shifts rely on the
 * complete target byte gate, not portable C semantics for arbitrary inputs.
 * The common ATfE build matches all 12 bytes, including the register shift.
 */
void
mclib_sample_filter_init(struct mclib_sample_filter *filter,
                         uint16_t shift, int16_t initial)
{
    filter->shift = shift;
    filter->accumulator = (initial << shift) - initial;
}

/* ITCM 0x4e38. Each valid SDK channel performs TWO volatile read/write pairs
 * on CHCTL2 at timer +0x20: first clear its enable bit, then OR the raw
 * enable argument shifted by the channel group. Do not combine the pairs or
 * normalize enable to a boolean. Complementary identifiers 16..19 clear
 * bits 2/6/10/14 but retain the same enable-argument shifts as 0..3.
 * Integer peripheral-address arithmetic reproduces stock's writeback LDRs.
 * The current 126-byte result still differs in switch block placement and
 * jump-table entries, so this helper is not yet byte exact.
 */

#elif defined(MCLIB_IO_HELPERS) || defined(MCLIB_CALIBRATE)

/* Calibration has its own source unit, preserving its observed call boundary
 * independently of the other PWM/acquisition helpers. */
#ifndef MCLIB_CALIBRATE

/* ITCM 0x3b38, reached by both flash control loops through veneer 0x080031b6.
 * Every assignment is a distinct volatile 32-bit timer write. The integer
 * peripheral-address member is re-read after each write, as in stock.
 * Conversion to unsigned truncates before converting the primary tick count
 * back to float for the fused extension calculation. Do not replace this
 * with a single float expression or collapse either bridge's write sequence.
 * The input is normally produced by mclib_pwm_prepare; no range checks or
 * clipping are present in stock. Out-of-range float-to-integer conversion
 * relies on target VCVT behavior, not portable C conversion semantics.
 * The current 228-byte build has both VFMA operations and all eight ordered
 * MMIO writes, but differs from the 228-byte stock in floating scheduling,
 * register assignment and reuse of the 15000.0f literal. It is not byte exact.
 */
void
mclib_pwm_update(struct mclib_pwm_state *pwm,
                  const struct mclib_pwm_pattern *pattern)
{
#define PWM_REGISTER(offset) (*(volatile uint32_t *)(pwm->timer + (offset)))
    uint8_t polarity = pattern->polarity;
    uint32_t alpha_positive = (uint32_t)((pattern->alpha_primary + 1.0f) * 7500.0f);
    uint32_t alpha_negative = (uint32_t)((1.0f - pattern->alpha_primary) * 7500.0f);
    float alpha_extended = pattern->alpha_extension * 15000.0f
                           + (float)alpha_positive;
    if (!(polarity & 1)) {
        PWM_REGISTER(0x34) = alpha_positive;
        PWM_REGISTER(0x64) = (uint32_t)alpha_extended;
        PWM_REGISTER(0x38) = alpha_negative;
        PWM_REGISTER(0x68) = alpha_positive;
    } else {
        PWM_REGISTER(0x34) = alpha_negative;
        PWM_REGISTER(0x64) = alpha_positive;
        PWM_REGISTER(0x38) = alpha_positive;
        PWM_REGISTER(0x68) = (uint32_t)alpha_extended;
    }

    uint32_t beta_negative = (uint32_t)((1.0f - pattern->beta_primary) * 7500.0f);
    uint32_t beta_positive = (uint32_t)((pattern->beta_primary + 1.0f) * 7500.0f);
    float beta_extended = pattern->beta_extension * 15000.0f
                          + (float)beta_positive;
    if (!(polarity & 2)) {
        PWM_REGISTER(0x3c) = beta_positive;
        PWM_REGISTER(0x6c) = (uint32_t)beta_extended;
        PWM_REGISTER(0x40) = beta_negative;
        PWM_REGISTER(0x70) = beta_positive;
    } else {
        PWM_REGISTER(0x3c) = beta_negative;
        PWM_REGISTER(0x6c) = beta_positive;
        PWM_REGISTER(0x40) = beta_positive;
        /* Resolve the final extension register only after the preceding
         * bridge writes; stock reloads the timer base again at 0x3c0e. */
        volatile uint32_t *beta_extension_register =
            (volatile uint32_t *)(pwm->timer + 0x70);
        *beta_extension_register = (uint32_t)beta_extended;
    }
#undef PWM_REGISTER
}


/* SDK timer-channel enable at ITCM 0x4e38 performs volatile read/modify/write
 * of timer +0x20. Keep its four calls: collapsing them changes MMIO accesses.
 * Sample filter init reaches flash 0x08000b28 via ITCM veneer 0x5bee.
 */

/* ITCM 0x3ad8, entered from flash through veneer 0x08003198. */
void
mclib_pwm_disable(void *pwm_output)
{
    struct mclib_pwm_state *pwm = pwm_output;
    timer_channel_output_state_config((uint32_t)pwm->timer, pwm->channels[0], 0);
    timer_channel_output_state_config((uint32_t)pwm->timer, pwm->channels[1], 0);
    timer_channel_output_state_config((uint32_t)pwm->timer, pwm->channels[2], 0);
    timer_channel_output_state_config((uint32_t)pwm->timer, pwm->channels[3], 0);
}

/* ITCM 0x39e0, entered from flash through veneer 0x080031ca. This starts
 * offset calibration; it does not clear the preceding peripheral settings or
 * last filtered samples. 8192 is the initial ADC midpoint for both channels.
 */
void
mclib_current_acquisition_reset(void *current_acquisition)
{
    struct mclib_current_acquisition_state *state = current_acquisition;
    state->offset_alpha = 8192;
    state->offset_beta = 8192;
    state->calibrating = 1;
    state->calibration_samples = 0;
    mclib_sample_filter_init(&state->alpha_filter, 8, 8192);
    mclib_sample_filter_init(&state->beta_filter, 8, 8192);
}

#endif
#ifdef MCLIB_CALIBRATE
/* ITCM 0x3a18, called by all four interrupt paths (0x28, 0x60, 0xae, 0xf6).
 * While calibration is active, sample only the signed low halfword of each
 * four-byte register slot. Commit offsets after at least 2000 samples and
 * return the remaining calibration flag, not a synthesized boolean.
 * Snapshot the counter before reading the peripheral sample, then store its
 * increment, as at 0x3a22/24/2a. The volatile shared status byte preserves the
 * final reload even on the inactive and just-completed paths. This full
 * 68-byte body is exact with the common compiler configuration.
 */
uint8_t
mclib_current_acquisition_calibrate(void *current_acquisition)
{
    struct mclib_current_acquisition_state *state = current_acquisition;
    if (state->calibrating) {
        uint16_t count = state->calibration_samples;
        int16_t sample_alpha = *(volatile int16_t *)&state->sample_registers[0];
        state->calibration_samples = count + 1;
        state->filtered_alpha = mclib_sample_filter_update(
            &state->alpha_filter, sample_alpha);
        state->filtered_beta = mclib_sample_filter_update(
            &state->beta_filter, *(volatile int16_t *)&state->sample_registers[1]);
        if (state->calibration_samples >= 2000) {
            state->calibrating = 0;
            state->offset_alpha = state->filtered_alpha;
            state->offset_beta = state->filtered_beta;
        }
    }
    return state->calibrating;
}
#endif

#elif defined(MCLIB_RESET_HELPER)

/* Flash-to-ITCM veneers 0x08003198 -> 0x3ad8 and 0x080031ca -> 0x39e0.
 * Hardware object layouts belong to their own source recovery. The former
 * disables four PWM channels; the latter initializes current sample filters.
 */

/* Flash 0x080011b0, called through ITCM veneer 0x5c0c. Configuration, timing
 * history, measured currents and most observer state deliberately survive.
 * Interrupt-facing gate and mode publications retain their observed byte
 * accesses. Threshold setup scheduling and the final acquisition-reset tail
 * call remain unmatched: 112 candidate bytes use the two alignment bytes at
 * 0x0800121e before the next real function at 0x08001220; no bytes are hidden.
 */
void
mclib_motor_reset(struct mclib_motor *motor)
{
    motor->raw_stall = 0;
    motor->stall_output = 0;
    *(volatile uint8_t *)&motor->stall_timing_gate = 1;
    *(volatile uint8_t *)&motor->idle_stall_gate = 0;
    motor->stall_gate_count = 0;
    motor->reset_work_060 = 0;
    motor->step_phase = 0x2000;
    motor->angle_increment = 0x4000;
    motor->microstep_exponent = 0;
    *(volatile uint8_t *)&motor->mode = 0;
    motor->idle_threshold = 0x7f281500;
    mclib_observer_reset(&motor->observer);
    mclib_pi_reset(&motor->d_current_pi);
    mclib_pi_reset(&motor->q_current_pi);
    mclib_pi_reset(&motor->auxiliary_pi);
    mclib_pwm_disable(motor->pwm_output);
    mclib_current_acquisition_reset(motor->current_acquisition);
}

#elif !defined(MCLIB_FLASH_HELPERS)

/* Match Klipper src/basecmd.h. The command address is the OID type token;
 * its linked Thumb address is 0x00000e41 in stock.
 */
extern void *oid_alloc(uint8_t oid, void *type, uint16_t size);
extern void *oid_lookup(uint8_t oid, void *type);

/* These cross-region calls resolve through ITCM veneers 0x5c02 and 0x5c16
 * to flash 0x08001710 and 0x08002e18. The former is not the registered init.
 * The latter enables the timer at 0x40000400 through 0x08003350.
 */
extern void mclib_hardware_init(void);

/* Registered initializer, ITCM 0x3d00. Initialization order is Y, X, Z, E,
 * whereas the externally indexed pointer table is X, Y, Z, E.
 * The common ATfE flags reproduce all 212 bytes, including both float pools.
 */
void
mclib_init(void)
{
    mclib_hardware_init();
    mclib_motor_reset(&mclib_motor_y);
    mclib_set_run_current(&mclib_motor_y, 1.5f);
    mclib_set_hold_current(&mclib_motor_y, 1.5f);
    mclib_set_microstep(&mclib_motor_y, 5);
    mclib_motor_reset(&mclib_motor_x);
    mclib_set_run_current(&mclib_motor_x, 1.5f);
    mclib_set_hold_current(&mclib_motor_x, 1.5f);
    mclib_set_microstep(&mclib_motor_x, 5);
    mclib_motor_reset(&mclib_motor_z);
    mclib_set_run_current(&mclib_motor_z, 0.8f);
    mclib_set_hold_current(&mclib_motor_z, 0.8f);
    mclib_set_microstep(&mclib_motor_z, 4);
    mclib_motor_reset(&mclib_motor_extruder);
    mclib_set_run_current(&mclib_motor_extruder, 0.55f);
    mclib_set_hold_current(&mclib_motor_extruder, 0.55f);
    mclib_set_microstep(&mclib_motor_extruder, 4);
    mclib_timer_start();
}

/* ITCM 0x00000e40; config_mclib oid=%c stepper=%u rs=%u ls=%u km=%u */
void
command_config_mclib(uint32_t *args)
{
    struct mclib_oid *binding = oid_alloc(args[0], command_config_mclib,
                                         sizeof(*binding));
    float resistance = (float)args[2] / 1000.0f;
    float inductance = (float)args[3] / 1000000.0f;
    float motor_constant = ((float)args[4] / 1000000.0f) / 50.0f;
    float kp = inductance * 6283.186f;
    float ki = (kp * (resistance / inductance)) * 5e-5f;
    /* VFMA at 0xeb6 rounds this multiplication/addition only once. Keep
     * floating expression contraction enabled, as in the verified ATfE build.
     */
    float plant_a = (-5e-5f / inductance) * resistance + 1.0f;

    binding->stepper = args[1];
    struct mclib_motor *motor = mclib_motors[args[1]];
    binding->motor = motor;
    motor->motor_constant = motor_constant;
    motor->inductance = inductance;
    motor->resistance = resistance;
    motor->d_current_pi.kp = kp;
    motor->d_current_pi.ki = ki;
    motor->q_current_pi.kp = kp;
    motor->q_current_pi.ki = ki;
    motor->observer.plant_a = plant_a;
    motor->observer.plant_b = 5e-5f / inductance;
}

/* ITCM 0x000018a8; mclib_config_microstep oid=%c interpolate=%c mstep=%u */
void
command_mclib_config_microstep(uint32_t *args)
{
    struct mclib_oid *binding = oid_lookup(args[0], command_config_mclib);
    struct mclib_motor *motor = binding->motor;
    uint16_t exponent = args[2];
    motor->interpolate = args[1];
    mclib_set_microstep(motor, exponent);
}

/* ITCM 0x000018d0; mclib_config_stalldetect oid=%c stallthrs=%u */
void
command_mclib_config_stalldetect(uint32_t *args)
{
    struct mclib_oid *binding = oid_lookup(args[0], command_config_mclib);
    binding->motor->stall_threshold = (float)args[1] / 1000.0f;
}

/* ITCM 0x00001910; mclib_set_current oid=%c run_current=%u hold_current=%u */
void
command_mclib_set_current(uint32_t *args)
{
    struct mclib_oid *binding = oid_lookup(args[0], command_config_mclib);
    mclib_set_run_current(binding->motor, (float)args[1] / 1000.0f);
    mclib_set_hold_current(binding->motor, (float)args[2] / 1000.0f);
}

/* ITCM 0x00001960; mclib_set_pid_params oid=%c kp=%u ki=%u */
void
command_mclib_set_pid_params(uint32_t *args)
{
    struct mclib_oid *binding = oid_lookup(args[0], command_config_mclib);
    float kp = (float)args[1] / 1000.0f;
    float ki = (float)args[2] / 1000.0f;
    binding->motor->d_current_pi.kp = kp;
    binding->motor->d_current_pi.ki = ki;
    binding->motor->q_current_pi.kp = kp;
    binding->motor->q_current_pi.ki = ki;
}

/* ITCM 0x00001900; mclib_identify_motor oid=%c umax=%u umin=%u
 * The stock command validates its OID but never loads umax or umin.
 */
void
command_mclib_identify_motor(uint32_t *args)
{
    (void)oid_lookup(args[0], command_config_mclib);
}

/* ITCM 0x000019a8; mclib_set_resonance_damp oid=%c tdx=%c amp=%u phase1=%u phase2=%u */
void
command_mclib_set_resonance_damp(uint32_t *args)
{
    struct mclib_oid *binding = oid_lookup(args[0], command_config_mclib);
    unsigned index = (args[1] >> 1) & 0xff;
    if (index > 2)
        return;
    float phase2 = (float)args[4] / 1000.0f;
    float amplitude = (float)args[2] / 1000.0f;
    float phase1 = (float)args[3] / 1000.0f;
    struct mclib_motor *motor = binding->motor;
    motor->resonance_amplitude[index] = amplitude;
    motor->resonance_phase1[index] = phase1;
    motor->resonance_phase2[index] = phase2;
}

#else /* MCLIB_FLASH_HELPERS */

/* Flash 0x08002e28. The loops pass normalized alpha/beta voltage in s0/s1,
 * and their embedded pattern (motor +0xd4) in r0. The signed comparisons
 * branch differently for NaNs than ordinary C < comparisons: unordered
 * magnitudes select the minimum primary value, while unordered signs set
 * their polarity bits. Preserve the independent subtract rounding for the
 * remainders, and do not add upper clipping absent from the firmware.
 * The current 140-byte build is not stock's 164-byte body: ATfE replaces the
 * branches with numeric-max/select instructions and speculates subtractions.
 * Final field formulas are recovered; instruction timing and FPSCR exception
 * behavior still require the complete byte gate before claiming equivalence.
 */
void
mclib_pwm_prepare(struct mclib_pwm_pattern *pattern, float alpha, float beta)
{
    float alpha_magnitude = __builtin_fabsf(alpha);
    float alpha_extension;
    if (!(alpha_magnitude >= 0.04f)) {
        pattern->alpha_primary = 0.04f;
        alpha_extension = 0.04f - alpha_magnitude;
    } else {
        pattern->alpha_primary = alpha_magnitude;
        alpha_extension = 0.0f;
    }
    pattern->alpha_extension = alpha_extension;
    pattern->alpha_remainder = (1.0f - pattern->alpha_primary) - alpha_extension;

    float beta_magnitude = __builtin_fabsf(beta);
    float beta_extension;
    if (!(beta_magnitude >= 0.04f)) {
        pattern->beta_primary = 0.04f;
        beta_extension = 0.04f - beta_magnitude;
    } else {
        pattern->beta_primary = beta_magnitude;
        beta_extension = 0.0f;
    }
    pattern->beta_extension = beta_extension;
    pattern->beta_remainder = (1.0f - pattern->beta_primary) - beta_extension;
    pattern->polarity = !(alpha >= 0.0f) | (!(beta >= 0.0f) << 1);
}

/* Flash 0x080015b8, reached through ITCM veneer 0x00005b62.
 * These natural unchecked shifts reconstruct the observed source operation.
 * Outside the normal exponent range, C does not define their behavior. The
 * complete 40-byte target match is the gate for preserving stock's ARM
 * register-shift behavior, including its low-byte count and >=32 rules.
 * Do not assume another compiler or a host build preserves those edge cases.
 */
void
mclib_set_microstep(struct mclib_motor *motor, uint16_t exponent)
{
    motor->angle_increment = 1u << (14u - exponent);
    motor->microstep_exponent = exponent;
    motor->idle_threshold = 0x007f2815u << (8u - exponent);
}

/* Flash 0x08001220, reached through ITCM veneer 0x00005b6c.
 * Hard-float ABI: motor in r0, current in s0 (Ghidra's prototype is wrong).
 * The assembly evaluates the division even for zero duration, then VSELEQ
 * selects delta. ATfE 22.1 reproduces all 52 bytes, including that VSELEQ and
 * the literal pool. GNU ARM 10.3 instead branches around the zero division.
 */
void
mclib_set_run_current(struct mclib_motor *motor, float current)
{
    motor->run_current = current;
    float delta = current - motor->hold_current;
    motor->hold_current_decrement = motor->current_transition_ticks
        ? delta / (float)motor->current_transition_ticks * 5000.0f : delta;
}

/* Flash 0x08001178, reached through ITCM veneer 0x00005b76.
 * VMINNM at 0x08001180 uses the numeric operand when only one is a quiet NaN.
 * The compiler fminf builtin expresses that operation, not a plain comparison.
 * ATfE 22.1 reproduces all 56 stock bytes, including VMINNM, VSELEQ and pool.
 */
void
mclib_set_hold_current(struct mclib_motor *motor, float current)
{
    current = __builtin_fminf(motor->run_current, current);
    motor->hold_current = current;
    float delta = motor->run_current - current;
    motor->hold_current_decrement = motor->current_transition_ticks
        ? delta / (float)motor->current_transition_ticks * 5000.0f : delta;
}

/* Flash 0x080020d0. The accumulator and final output have independent limits.
 * Separate product statements preserve stock's non-fused VMLA rounding;
 * contracting them into FMA changes the arithmetic for some finite inputs.
 * The lower comparisons use !(value >= minimum): stock's signed LT condition
 * also takes the lower clamp on unordered/NaN inputs. An ordinary C < test
 * would change that behavior. The post-clamp accumulator reload at 0x08002112
 * is an explicit access to controller state, also published by reset/config.
 * Local volatile views preserve that read instead of forwarding the local
 * accumulator, and the subsequent output-minimum snapshot at 0x0800211a.
 * The minimum is read once, after the accumulator reload, not speculatively
 * before it. The full 116-byte helper matches under the shared configuration.
 */
float
mclib_pi_step(struct mclib_pi *pi, float target, float measured)
{
    float error = target - measured;
    pi->error = error;
    float integral_delta = error * pi->ki;
    float integral = pi->integral + integral_delta;
    pi->integral = integral;
    if (integral > pi->integral_max)
        pi->integral = pi->integral_max;
    else if (!(integral >= pi->integral_min))
        pi->integral = pi->integral_min;

    float proportional = error * pi->kp;
    float output = *(volatile float *)&pi->integral + proportional;
    float minimum = *(volatile float *)&pi->output_min;
    if (!(output >= minimum))
        output = minimum;
    else if (output > pi->output_max)
        output = pi->output_max;
    pi->output = output;
    return output;
}

/* Flash 0x08002148. Gains and limits survive a controller reset. */
void
mclib_pi_reset(struct mclib_pi *pi)
{
    pi->integral = 0.0f;
    pi->error = 0.0f;
    pi->output = 0.0f;
}

/* Flash 0x080020b0, called with sine/cosine from 0x08002970. Both output
 * values are computed before either store, matching potentially aliased
 * output pointers. VMLA/VMLS here are non-fused operations.
 * The current compiler exchanges multiplication operands and the first
 * accumulation term; exact instruction bytes remain a gate, including any
 * NaN-payload effects of those operand exchanges.
 */
void
mclib_park(float alpha, float beta, float sine, float cosine,
           float *d_current, float *q_current)
{
    float beta_sin = sine * beta;
    float alpha_cos = cosine * alpha;
    float beta_cos = cosine * beta;
    float alpha_sin = sine * alpha;
    float d = alpha_cos + beta_sin;
    float q = beta_cos - alpha_sin;
    *d_current = d;
    *q_current = q;
}

/* Flash 0x08002c48, called by motor reset at 0x080011f0 with motor +0xf0.
 * Parameters, current angle, and speed fields deliberately survive this reset.
 * Later observer integration must preserve its helper boundaries: angle wrap
 * at 0x08000848 is a repeated-add/subtract algorithm with a NaN-loop edge case,
 * and sqrt at 0x08002df8 executes VSQRT only on the positive branch. Current
 * compiler loop merging still differs for angle wrap; square root now has an
 * independently byte-exact SDK-intrinsic reconstruction. Neither helper is
 * replaced with a host/library approximation here.
 */
void
mclib_observer_reset(struct mclib_observer *observer)
{
    observer->previous_angle = 0.0f;
    observer->estimated_alpha_current = 0.0f;
    observer->estimated_beta_current = 0.0f;
    observer->filtered_alpha_emf = 0.0f;
    observer->filtered_beta_emf = 0.0f;
}

#endif /* MCLIB_FLASH_HELPERS */
