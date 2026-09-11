/* mainBoardGD lookup-based trigonometry. No libm substitution is used:
 * quadrant constants differ by a few ULPs, wrapping repeatedly rounds, and
 * interpolation consists of non-fused VMLA/VNMLS operations. Complete
 * instruction/literal gates are in check-gd-trig.py.
 */
#include <stdint.h>

#if defined(GD_TRIG_TABLES)

/* Flash 0x0800352c..0x08003738, 131 * 4 bytes. Stock decimal-rounded
 * samples of sin((i-1)*pi/256), including both interpolation guards. Hex
 * literals preserve those existing float values without recomputing libm.
 */
const float mclib_sine_table[131] = {
    -0x1.921ccep-7f, 0x0p+0f, 0x1.921ccep-7f, 0x1.921540p-6f,
    0x1.2d864cp-5f, 0x1.91f638p-5f, 0x1.f656d4p-5f, 0x1.2d51f8p-4f,
    0x1.5f6cfep-4f, 0x1.917a60p-4f, 0x1.c3785ap-4f, 0x1.f564d2p-4f,
    0x1.139f0cp-3f, 0x1.2c80fcp-3f, 0x1.455766p-3f, 0x1.5e2138p-3f,
    0x1.76dd92p-3f, 0x1.8f8b80p-3f, 0x1.a829f8p-3f, 0x1.c0b822p-3f,
    0x1.d934fep-3f, 0x1.f19f8cp-3f, 0x1.04fb7cp-2f, 0x1.111d22p-2f,
    0x1.1d343ep-2f, 0x1.29405ep-2f, 0x1.354108p-2f, 0x1.4135c6p-2f,
    0x1.4d1e1ep-2f, 0x1.58f9a4p-2f, 0x1.64c7d8p-2f, 0x1.708850p-2f,
    0x1.7c3a8cp-2f, 0x1.87de28p-2f, 0x1.9372a4p-2f, 0x1.9ef794p-2f,
    0x1.aa6c7ep-2f, 0x1.b5d0fap-2f, 0x1.c1249ap-2f, 0x1.cc66e8p-2f,
    0x1.d79774p-2f, 0x1.e2b5d2p-2f, 0x1.edc190p-2f, 0x1.f8ba48p-2f,
    0x1.01cfc6p-1f, 0x1.073878p-1f, 0x1.0c9702p-1f, 0x1.11eb34p-1f,
    0x1.1734d4p-1f, 0x1.1c73b2p-1f, 0x1.21a79ap-1f, 0x1.26d052p-1f,
    0x1.2bedb0p-1f, 0x1.30ff80p-1f, 0x1.36058ap-1f, 0x1.3affa0p-1f,
    0x1.3fed92p-1f, 0x1.44cf30p-1f, 0x1.49a448p-1f, 0x1.4e6caap-1f,
    0x1.532826p-1f, 0x1.57d692p-1f, 0x1.5c77bcp-1f, 0x1.610b74p-1f,
    0x1.659190p-1f, 0x1.6a09e4p-1f, 0x1.6e7444p-1f, 0x1.72d080p-1f,
    0x1.771e74p-1f, 0x1.7b5df2p-1f, 0x1.7f8eccp-1f, 0x1.83b0e0p-1f,
    0x1.87c3fep-1f, 0x1.8bc804p-1f, 0x1.8fbccap-1f, 0x1.93a224p-1f,
    0x1.9777f0p-1f, 0x1.9b3e04p-1f, 0x1.9ef440p-1f, 0x1.a29a7ap-1f,
    0x1.a63092p-1f, 0x1.a9b662p-1f, 0x1.ad2bcap-1f, 0x1.b090a4p-1f,
    0x1.b3e4d0p-1f, 0x1.b72834p-1f, 0x1.ba5aa4p-1f, 0x1.bd7c08p-1f,
    0x1.c08c40p-1f, 0x1.c38b2cp-1f, 0x1.c678b2p-1f, 0x1.c954b2p-1f,
    0x1.cc1f0ep-1f, 0x1.ced7acp-1f, 0x1.d17e74p-1f, 0x1.d4134cp-1f,
    0x1.d69616p-1f, 0x1.d906bcp-1f, 0x1.db6524p-1f, 0x1.ddb13cp-1f,
    0x1.dfeae6p-1f, 0x1.e2120ep-1f, 0x1.e426a4p-1f, 0x1.e6288cp-1f,
    0x1.e817bap-1f, 0x1.e9f414p-1f, 0x1.ebbd8cp-1f, 0x1.ed740cp-1f,
    0x1.ef1788p-1f, 0x1.f0a7eep-1f, 0x1.f2252ep-1f, 0x1.f38f3ap-1f,
    0x1.f4e602p-1f, 0x1.f6297ap-1f, 0x1.f75998p-1f, 0x1.f8764ep-1f,
    0x1.f97f92p-1f, 0x1.fa7558p-1f, 0x1.fb5796p-1f, 0x1.fc2646p-1f,
    0x1.fce15ep-1f, 0x1.fd88dap-1f, 0x1.fe1cb0p-1f, 0x1.fe9cd8p-1f,
    0x1.ff0956p-1f, 0x1.ff621cp-1f, 0x1.ffa72cp-1f, 0x1.ffd886p-1f,
    0x1.fff622p-1f, 0x1p+0f, 0x1.fff622p-1f,
};
_Static_assert(sizeof(mclib_sine_table) == 524, "stock guarded sine table size");

#else

/* Guarded quarter-wave samples at 0x0800352c..0x08003738. Element 1 is
 * sin(0), element 129 is sin(pi/2), and elements 0/130 are the guard samples.
 */
extern const float mclib_sine_table[131];

#if defined(GD_TRIG_SINE)

/* Flash 0x08002b50..0x08002c48, including all seven literals. No bounds
 * check or clamp is added to signed VCVT-derived indices. NaN/Inf (and
 * sufficiently large finite inputs whose subtraction rounds away) may loop
 * indefinitely during wrapping, as in stock.
 * Candidate is 248/248 bytes, with 85 matching: it speculates reflected
 * quadrant arithmetic and uses VSEL where stock branches. All formulas and
 * constants are retained, but FPSCR exception timing is not proven equal.
 */
float
mclib_sine(float angle)
{
    while (angle >= 0x1.921fb6p+2f)
        angle += -0x1.921fb6p+2f;
    while (!(angle >= 0.0f))
        angle += 0x1.921fb6p+2f;

    if (!(angle >= 0x1.921fb4p+1f)) {
        if (angle >= 0x1.921fb4p+0f)
            angle = 0x1.921fb4p+1f - angle;
        float scaled = angle * 0x1.45f306p+6f;
        int32_t index = (int32_t)scaled;
        float fraction = scaled - __builtin_elementwise_trunc(scaled);
        float base = mclib_sine_table[index + 1];
        float delta = mclib_sine_table[index + 2] - base;
        float product = fraction * delta;
        return base + product;
    } else {
        if (!(angle >= 0x1.2d97c8p+2f))
            angle += -0x1.921fb4p+1f;
        else
            angle = 0x1.921fb6p+2f - angle;
        float scaled = angle * 0x1.45f306p+6f;
        int32_t index = (int32_t)scaled;
        float fraction = __builtin_elementwise_trunc(scaled) - scaled;
        float base = mclib_sine_table[index + 1];
        float delta = mclib_sine_table[index + 2] - base;
        float product = fraction * delta;
        return product - base;
    }
}

#else

/* Flash 0x08002970..0x08002b50, including all seven literals. Hard-float
 * ABI: angle=s0, sine pointer=r0, cosine pointer=r1. Both values are computed
 * before sine-then-cosine stores, retaining the observed aliasing behavior.
 * Complementary table indices avoid an extra angle addition for cosine.
 * The complementary cosine samples are adjacent: sample 128-index is the
 * next value and sample 129-index is the base. Expressing that shared address
 * avoids duplicate index arithmetic without changing the FP formulas. The
 * candidate fits the stock allocation, but independent-operation scheduling,
 * register allocation and the shared positive-sine tail remain unmatched.
 */
void
mclib_sincos(float angle, float *sine, float *cosine)
{
    while (angle >= 0x1.921fb6p+2f)
        angle += -0x1.921fb6p+2f;
    while (!(angle >= 0.0f))
        angle += 0x1.921fb6p+2f;

    float sine_value, cosine_value;
    if (!(angle >= 0x1.921fb4p+1f)) {
        if (!(angle >= 0x1.921fb4p+0f)) {
            float scaled = angle * 0x1.45f306p+6f;
            int32_t index = (int32_t)scaled;
            float fraction = scaled - __builtin_elementwise_trunc(scaled);
            float sine_base = mclib_sine_table[index + 1];
            const float *cosine_samples = &mclib_sine_table[128 - index];
            float cosine_base = cosine_samples[1];
            float sine_next = mclib_sine_table[index + 2];
            float cosine_next = cosine_samples[0];
            float sine_delta = sine_next - sine_base;
            float cosine_delta = cosine_next - cosine_base;
            float cosine_product = fraction * cosine_delta;
            float sine_product = fraction * sine_delta;
            cosine_value = cosine_base + cosine_product;
            sine_value = sine_base + sine_product;
        } else {
            float scaled = (0x1.921fb4p+1f - angle) * 0x1.45f306p+6f;
            int32_t index = (int32_t)scaled;
            float fraction = scaled - __builtin_elementwise_trunc(scaled);
            float sine_base = mclib_sine_table[index + 1];
            const float *cosine_samples = &mclib_sine_table[128 - index];
            float cosine_base = cosine_samples[1];
            float sine_next = mclib_sine_table[index + 2];
            float cosine_next = cosine_samples[0];
            float sine_delta = sine_next - sine_base;
            float cosine_delta = cosine_base - cosine_next;
            float cosine_product = fraction * cosine_delta;
            float sine_product = fraction * sine_delta;
            cosine_value = cosine_product - cosine_base;
            sine_value = sine_base + sine_product;
        }
    } else {
        if (!(angle >= 0x1.2d97c8p+2f)) {
            float scaled = (angle + -0x1.921fb4p+1f) * 0x1.45f306p+6f;
            int32_t index = (int32_t)scaled;
            float fraction = scaled - __builtin_elementwise_trunc(scaled);
            float sine_base = mclib_sine_table[index + 1];
            const float *cosine_samples = &mclib_sine_table[128 - index];
            float cosine_base = cosine_samples[1];
            float sine_next = mclib_sine_table[index + 2];
            float cosine_next = cosine_samples[0];
            float sine_delta = sine_base - sine_next;
            float cosine_delta = cosine_base - cosine_next;
            float cosine_product = fraction * cosine_delta;
            float sine_product = fraction * sine_delta;
            cosine_value = cosine_product - cosine_base;
            sine_value = sine_product - sine_base;
        } else {
            float scaled = (0x1.921fb6p+2f - angle) * 0x1.45f306p+6f;
            int32_t index = (int32_t)scaled;
            float fraction = scaled - __builtin_elementwise_trunc(scaled);
            float sine_base = mclib_sine_table[index + 1];
            const float *cosine_samples = &mclib_sine_table[128 - index];
            float cosine_base = cosine_samples[1];
            float sine_next = mclib_sine_table[index + 2];
            float cosine_next = cosine_samples[0];
            float sine_delta = sine_base - sine_next;
            float cosine_delta = cosine_next - cosine_base;
            float cosine_product = fraction * cosine_delta;
            float sine_product = fraction * sine_delta;
            cosine_value = cosine_base + cosine_product;
            sine_value = sine_product - sine_base;
        }
    }
    *sine = sine_value;
    *cosine = cosine_value;
}

#endif /* GD_TRIG_SINE */
#endif /* GD_TRIG_TABLES */
