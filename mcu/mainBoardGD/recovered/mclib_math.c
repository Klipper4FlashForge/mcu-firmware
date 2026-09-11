/* mainBoardGD motor arithmetic, complete C bodies gated by check-gd-math.py.
 * The observer and limiter are separate translation units from leaf math:
 * their observed calls must survive normal compilation without attributes.
 * No host-library substitutes are used for the remaining stock angle/table
 * helpers. FP operation order is explicit where stock uses non-fused VMLA;
 * until a complete byte match, FPSCR and NaN-payload effects remain unproven.
 */
#include "mclib_state.h"

#if defined(MCLIB_MATH_OBSERVER)

/* Real stock dependencies, not replacement bodies. The angle approximation
 * is table-based, not a claim that the stock routine is a libm atan2f.
 */
extern float mclib_atan2(float y, float x);
extern void mclib_observer_velocity_update(struct mclib_observer *observer);
extern float mclib_wrap_angle(float angle);

/* Flash 0x08002c58..0x08002d6c, including the 0x45a39fe9 filter-frequency
 * literal. Saturated sliding-mode observer: current prediction errors drive
 * bounded correction voltages, whose filtered values estimate back EMF.
 * The lower saturation test deliberately includes unordered comparisons,
 * matching BGE's not-taken NaN path at 0x2c94 / 0x2cc8.
 */
void
mclib_observer_update(struct mclib_observer *observer,
                      float alpha_voltage, float beta_voltage,
                      float alpha_current, float beta_current)
{
    float estimated_alpha = observer->estimated_alpha_current;
    float estimated_beta = observer->estimated_beta_current;
    float alpha_error = estimated_alpha - alpha_current;
    float beta_error = estimated_beta - beta_current;
    float limit = observer->error_limit;
    observer->alpha_current_error = alpha_error;
    observer->beta_current_error = beta_error;

    float alpha_correction;
    if (alpha_error > limit)
        alpha_correction = observer->sliding_gain;
    else if (!(alpha_error >= -limit))
        alpha_correction = -observer->sliding_gain;
    else
        alpha_correction = alpha_error * observer->sliding_slope;
    observer->alpha_sliding_voltage = alpha_correction;

    float beta_correction;
    if (beta_error > limit)
        beta_correction = observer->sliding_gain;
    else if (!(beta_error >= -limit))
        beta_correction = -observer->sliding_gain;
    else
        beta_correction = beta_error * observer->sliding_slope;

    float alpha_drive = observer->plant_b * (alpha_voltage - observer->alpha_sliding_voltage);
    float beta_drive = observer->plant_b * (beta_voltage - beta_correction);
    float alpha_memory = estimated_alpha * observer->plant_a;
    float beta_memory = estimated_beta * observer->plant_a;
    float old_alpha_emf = observer->filtered_alpha_emf;
    float old_beta_emf = observer->filtered_beta_emf;
    float alpha_filter = (observer->alpha_sliding_voltage - old_alpha_emf)
                         * observer->emf_filter_gain;
    float beta_filter = observer->emf_filter_gain * (beta_correction - old_beta_emf);
    observer->beta_sliding_voltage = beta_correction;
    observer->estimated_alpha_current = alpha_drive + alpha_memory;
    observer->filtered_alpha_emf = old_alpha_emf + alpha_filter;
    observer->estimated_beta_current = beta_drive + beta_memory;
    observer->filtered_beta_emf = old_beta_emf + beta_filter;

    observer->angle = mclib_atan2(-observer->filtered_alpha_emf,
                                 observer->filtered_beta_emf);
    mclib_observer_velocity_update(observer);
    observer->angle_compensation = mclib_atan2(observer->filtered_angular_velocity,
                                               0x1.473fd2p+12f);
    observer->angle = observer->angle_compensation + observer->angle;
    observer->angle = mclib_wrap_angle(observer->angle);
}

#elif defined(MCLIB_MATH_LIMIT)

/* Flash 0x080015e0..0x08001670, including all three constants. D priority:
 * excessive D sets Q to zero; otherwise limit Q to the remaining circle.
 * Unordered D clamps negative, unordered magnitude returns unchanged, and
 * unordered Q selects the negative root. No "safe" NaN handling is added.
 * The two D-clamp paths share the Q-zero store; circle limiting must remain
 * in the other branch so no FP arithmetic is speculated for clamped D.
 */
void
mclib_limit_dq_voltage(struct mclib_motor *motor)
{
    float d = motor->d_voltage;
    if (d > 23.99f) {
        motor->d_voltage = 23.99f;
    } else if (!(d >= -23.99f)) {
        motor->d_voltage = -23.99f;
    } else {
        float d_squared = d * d;
        float q = motor->q_voltage;
        float q_squared = q * q;
        float magnitude_squared = d_squared + q_squared;
        if (magnitude_squared > 0x1.1fc292p+9f) {
            float limited = mclib_sqrt_positive(0x1.1fc292p+9f - d_squared);
            if (!(motor->q_voltage >= 0.0f))
                limited = -limited;
            motor->q_voltage = limited;
        }
        return;
    }
    motor->q_voltage = 0.0f;
}

#else

#include "arm_math_intrinsics.h"

/* Flash 0x08002950..0x0800296a. Compute both before storing so aliased
 * output pointers retain the observed alpha-then-beta store semantics.
 */
void
mclib_inverse_park(float d, float q, float sine, float cosine,
                   float *alpha, float *beta)
{
    float d_cos = cosine * d;
    float d_sin = sine * d;
    float q_sin = sine * q;
    float q_cos = cosine * q;
    float transformed_alpha = d_cos - q_sin;
    float transformed_beta = d_sin + q_cos;
    *alpha = transformed_alpha;
    *beta = transformed_beta;
}

/* Flash 0x08002df8..0x08002e14, including the positive-zero literal.
 * Stock executes VSQRT only for ordered positive inputs; negative values,
 * signed zeros and NaNs return +0. The documented SDK intrinsic keeps VSQRT
 * inside this C condition; an elementwise builtin speculates it and adds IOC
 * for negative inputs. The complete 28-byte function and pool are exact.
 */
float
mclib_sqrt_positive(float value)
{
    if (value > 0.0f)
        return gd_arm_sqrtf(value);
    return 0.0f;
}

#endif
