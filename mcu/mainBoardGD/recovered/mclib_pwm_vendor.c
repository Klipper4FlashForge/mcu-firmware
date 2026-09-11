/* mainBoardGD motor PWM/current interface, complete stock function spans.
 * PWM_CHANNEL builds the observed out-of-line channel initializer; the other
 * unit owns the public entry points. No new storage or executable data.
 */
#include "mclib_hardware.h"

void mclib_pwm_channel_init(struct mclib_pwm_state *, uint16_t);

#if defined(PWM_CHANNEL)

/* 0x3c20..0x3c82: initialize one SDK channel. The twelve-byte parameter
 * is explicitly cleared after the SDK defaults call, as in stock. Clear
 * the idle field first to retain stock's final-word-first store order.
 * Current complete candidate is 90/98 bytes; stock still pairs two stores.
 */
void
mclib_pwm_channel_init(struct mclib_pwm_state *pwm, uint16_t channel)
{
    timer_oc_parameter_struct parameter;
    timer_channel_output_struct_para_init(&parameter);
    parameter.ocidlestate = 0;
    parameter.outputstate = 0;
    parameter.outputnstate = 0;
    parameter.ocpolarity = 0;
    parameter.ocnpolarity = 0;
    parameter.ocnidlestate = 0;
    timer_channel_output_config(pwm->timer, channel, &parameter);
    timer_channel_output_mode_config(pwm->timer, channel, 0x60);
    timer_channel_output_shadow_config(pwm->timer, channel, 8);
    timer_channel_output_pulse_value_config(pwm->timer, channel, 0);
    timer_channel_composite_pwm_mode_config(pwm->timer, channel, 1);
    timer_channel_additional_output_shadow_config(pwm->timer, channel, 1);
    timer_channel_additional_compare_value_config(pwm->timer, channel, 0);
}

#else

/* 0x3a60..0x3a64. Upper argument bits do not reach the byte field. */
void
mclib_current_acquisition_set_polarity(
    struct mclib_current_acquisition_state *state, uint8_t polarity)
{
    state->polarity = polarity;
}

/* 0x3a68..0x3ad8, including three floats at 0x3acc. Stock reads signed
 * halfwords at sample +0/+4, not full-width MMIO words. Each difference is
 * multiplied before adding the fixed signed offset; no fused operation.
 */
void
mclib_current_acquisition_read(struct mclib_current_acquisition_state *state)
{
    volatile int16_t *samples = (volatile int16_t *)state->sample_registers;
    int32_t offset_alpha = state->offset_alpha;
    int32_t alpha = samples[0] - offset_alpha;
    int32_t beta = samples[2] - state->offset_beta;
    float alpha_current = (float)alpha * 0x1.19999ap-12f;
    float beta_current = (float)beta * 0x1.19999ap-12f;
    state->measured_alpha = !(state->polarity & 1)
                            ? alpha_current - 0.04f : 0.04f - alpha_current;
    state->measured_beta = !(state->polarity & 2)
                           ? beta_current - 0.04f : 0.04f - beta_current;
}

/* 0x3b08..0x3b38. The public ABI matches the existing disable entry. */
void
mclib_pwm_enable(void *pwm_output)
{
    struct mclib_pwm_state *pwm = pwm_output;
    timer_channel_output_state_config(pwm->timer, pwm->channels[0], 1);
    timer_channel_output_state_config(pwm->timer, pwm->channels[1], 1);
    timer_channel_output_state_config(pwm->timer, pwm->channels[2], 1);
    timer_channel_output_state_config(pwm->timer, pwm->channels[3], 1);
}

/* 0x3c88..0x3cfc. SDK defaults preserve padding halfwords, and this caller
 * does too. Only TIMER0/TIMER7 (0x40010000/0x40010400) enable the primary
 * output gate; initialization does not start the timer or enable channels.
 * Initialize direction before the neighboring mode fields. This preserves
 * the full parameter/call behavior and gives 99/116 matching bytes; paired
 * loads/stores still differ from stock's sequence at 0x3c9c..0x3cb8.
 */
void
mclib_pwm_init(struct mclib_pwm_state *pwm)
{
    timer_deinit(pwm->timer);
    timer_parameter_struct parameter;
    timer_struct_para_init(&parameter);
    parameter.counterdirection = 0;
    parameter.prescaler = 0;
    parameter.alignedmode = 0;
    parameter.period = 2u * pwm->half_period_ticks - 1u;
    parameter.clockdivision = 0;
    parameter.repetitioncounter = 0;
    timer_init(pwm->timer, &parameter);
    mclib_pwm_channel_init(pwm, pwm->channels[0]);
    mclib_pwm_channel_init(pwm, pwm->channels[1]);
    mclib_pwm_channel_init(pwm, pwm->channels[2]);
    mclib_pwm_channel_init(pwm, pwm->channels[3]);
    if (pwm->timer == 0x40010000u || pwm->timer == 0x40010400u)
        timer_primary_output_config(pwm->timer, 1);
}

#endif
