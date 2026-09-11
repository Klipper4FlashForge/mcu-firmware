/* Complete mainBoardGD angle helpers, gated by check-gd-angles.py.
 * Constants intentionally preserve stock's different pi roundings.
 * Remaining instruction/FPSCR differences are not mathematical equivalence
 * claims. In particular the stock wrap loops do not terminate for NaN/Inf.
 */
#include "mclib_state.h"

#if defined(GD_ANGLE_TABLES)

/* Flash 0x0800338c..0x08003524, 102 * 4 bytes. These are numeric atan
 * samples, not instructions. Exact hexadecimal literals retain the stock
 * decimal-table rounding; recomputing atan(i/100) would change some bits.
 * The endpoint i=101 is loaded by the clamped index-100 branches at
 * 0x0934/0x0942, 0x0a16/0x0a20 and 0x0ad2/0x0adc.
 */
const float mclib_atan_table[102] = {
    0x0p+0f, 0x1.47aabap-7f, 0x1.47a2c2p-6f, 0x1.eb5f60p-6f,
    0x1.478134p-5f, 0x1.994226p-5f, 0x1.eaee56p-5f, 0x1.1e40c8p-4f,
    0x1.46fbb8p-4f, 0x1.6fa630p-4f, 0x1.983e1ap-4f, 0x1.c0c176p-4f,
    0x1.e92e48p-4f, 0x1.08c154p-3f, 0x1.1cde50p-3f, 0x1.30ed30p-3f,
    0x1.44ed04p-3f, 0x1.58dce8p-3f, 0x1.6cbbf8p-3f, 0x1.808950p-3f,
    0x1.944418p-3f, 0x1.a7eb7ap-3f, 0x1.bb7ebap-3f, 0x1.cefce6p-3f,
    0x1.e2655ep-3f, 0x1.f5b758p-3f, 0x1.04790cp-2f, 0x1.0e0a78p-2f,
    0x1.178f98p-2f, 0x1.210816p-2f, 0x1.2a73a0p-2f, 0x1.33d1f4p-2f,
    0x1.3d22c2p-2f, 0x1.4665bep-2f, 0x1.4f9aaep-2f, 0x1.58c148p-2f,
    0x1.61d94ep-2f, 0x1.6ae290p-2f, 0x1.73dccep-2f, 0x1.7cc7d2p-2f,
    0x1.85a372p-2f, 0x1.8e6f80p-2f, 0x1.972bc4p-2f, 0x1.9fd828p-2f,
    0x1.a87478p-2f, 0x1.b1009cp-2f, 0x1.b97c6cp-2f, 0x1.c1e7ccp-2f,
    0x1.ca42a8p-2f, 0x1.d28ce6p-2f, 0x1.dac670p-2f, 0x1.e2ef2cp-2f,
    0x1.eb0714p-2f, 0x1.f30e1cp-2f, 0x1.fb0432p-2f, 0x1.0174aap-1f,
    0x1.055eb8p-1f, 0x1.094046p-1f, 0x1.0d194ep-1f, 0x1.10e9d8p-1f,
    0x1.14b1dep-1f, 0x1.187160p-1f, 0x1.1c2866p-1f, 0x1.1fd6f0p-1f,
    0x1.237d02p-1f, 0x1.271aa6p-1f, 0x1.2aafdep-1f, 0x1.2e3caep-1f,
    0x1.31c122p-1f, 0x1.353d40p-1f, 0x1.38b110p-1f, 0x1.3c1c9cp-1f,
    0x1.3f7ff2p-1f, 0x1.42db14p-1f, 0x1.462e14p-1f, 0x1.4978fap-1f,
    0x1.4cbbd0p-1f, 0x1.4ff6a8p-1f, 0x1.532986p-1f, 0x1.565482p-1f,
    0x1.5977a4p-1f, 0x1.5c92f8p-1f, 0x1.5fa68ep-1f, 0x1.62b276p-1f,
    0x1.65b6bcp-1f, 0x1.68b370p-1f, 0x1.6ba8a4p-1f, 0x1.6e9662p-1f,
    0x1.717cbcp-1f, 0x1.745bc4p-1f, 0x1.77338ap-1f, 0x1.7a0418p-1f,
    0x1.7ccd86p-1f, 0x1.7f8fe2p-1f, 0x1.824b38p-1f, 0x1.84ff9ep-1f,
    0x1.87ad22p-1f, 0x1.8a53d8p-1f, 0x1.8cf3c8p-1f, 0x1.8f8d0cp-1f,
    0x1.921fb4p-1f, 0x1.94abccp-1f,
};
_Static_assert(sizeof(mclib_atan_table) == 408, "stock atan table size");

#elif defined(GD_ANGLE_ATAN)

/* 102 actual binary32 samples at flash 0x0800338c..0x08003524, approximating
 * atan(i/100), i=0..101. The final sample is needed by index-100 interpolation.
 */
extern const float mclib_atan_table[102];

/* Flash 0x08000890..0x08000b10: eight octants, linearly interpolated table.
 * ABI is hard-float y=s0, x=s1, result=s0. x==0 returns +0 for EVERY y;
 * this is the observed approximation, not a standard atan2f replacement.
 * Integer conversion is signed VCVT; only three octants clamp its unsigned
 * interpretation to 100. Unclamped out-of-range/NaN conversion and table
 * indexing retain C/compiler limitations, not invented domain checks.
 * VRINTZ supplies the fraction independently of the converted table index.
 * Products stay separate to represent non-fused VMLA/VNMLS rounding, and
 * quadrant offsets are added at the particular stage observed in stock.
 * Common-profile candidate is 640 bytes, 599 matching. Remaining differences
 * are reversed comparison operands/conditions at 0x08a8 and 0x09e4, and
 * constant scheduling/register assignment in the 0x0910..0x0952 octant.
 */
float
mclib_atan2(float y, float x)
{
    if (x > 0.0f) {
        if (!(y >= 0.0f)) {
            if (-y > x) {
                float scaled = (x * 100.0f) / -y;
                int32_t index = (int32_t)scaled;
                float fraction = scaled - __builtin_elementwise_trunc(scaled);
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return (base + product) + 0x1.2d97c8p+2f;
            } else {
                float scaled = (y * -100.0f) / x;
                int32_t index = (int32_t)scaled;
                float fraction = __builtin_elementwise_trunc(scaled) - scaled;
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return (product - base) + 0x1.921fb6p+2f;
            }
        } else {
            if (y > x) {
                float scaled = (x * 100.0f) / y;
                int32_t index = (int32_t)scaled;
                float fraction = __builtin_elementwise_trunc(scaled) - scaled;
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return (product - base) + 0x1.921fb4p+0f;
            } else {
                float scaled = (y * 100.0f) / x;
                int32_t index = (int32_t)scaled;
                float fraction = scaled - __builtin_elementwise_trunc(scaled);
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return base + product;
            }
        }
    } else if (!(x >= 0.0f)) {
        if (!(y >= 0.0f)) {
            if (y > x) {
                float scaled = (y * 100.0f) / x;
                uint32_t index = (int32_t)scaled;
                float fraction = scaled - __builtin_elementwise_trunc(scaled);
                if (index >= 100)
                    index = 100;
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float shifted_base = base + 0x1.921fb4p+1f;
                float product = fraction * delta;
                return shifted_base + product;
            } else {
                float scaled = (x * 100.0f) / y;
                int32_t index = (int32_t)scaled;
                float fraction = __builtin_elementwise_trunc(scaled) - scaled;
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return (product - base) + 0x1.2d97c8p+2f;
            }
        } else {
            if (-x >= y) {
                float scaled = (y * 100.0f) / -x;
                uint32_t index = (int32_t)scaled;
                float fraction = __builtin_elementwise_trunc(scaled) - scaled;
                if (index >= 100)
                    index = 100;
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return (product - base) + 0x1.921fb4p+1f;
            } else {
                float scaled = (x * -100.0f) / y;
                uint32_t index = (int32_t)scaled;
                float fraction = scaled - __builtin_elementwise_trunc(scaled);
                if (index >= 100)
                    index = 100;
                float base = mclib_atan_table[index];
                float delta = mclib_atan_table[index + 1] - base;
                float product = fraction * delta;
                return (base + product) + 0x1.921fb4p+0f;
            }
        }
    }
    return 0.0f;
}

#else

/* Flash 0x08000848..0x08000890 including two binary32 literals. The first
 * loop subtracts 2*pi for ordered angle>=2*pi. The second loop's BLT also
 * takes unordered, so its C comparison deliberately keeps NaN looping.
 * This is not fmod: it repeatedly rounds after each addition/subtraction.
 * Candidate is 60/72 bytes: the compiler merges loop entry/exit paths.
 * An explicit early-return/do-while form emitted the same candidate.
 */
float
mclib_wrap_angle(float angle)
{
    while (angle >= 0x1.921fb6p+2f)
        angle += -0x1.921fb6p+2f;
    while (!(angle >= 0.0f))
        angle += 0x1.921fb6p+2f;
    return angle;
}

/* Flash 0x08002d70..0x08002df8 including all seven literals. Differentiate
 * the uncorrected observer angle, wrap once across +/-pi, then apply a 0.1
 * first-order velocity filter. The lower wrap takes unordered comparisons;
 * upper/lower are mutually exclusive, unlike the full-angle wrap helper.
 * Stock leaves the final scaled velocity in s0, but its only observed caller
 * ignores it; retain the existing void ABI rather than infer a return value.
 * Candidate is 132/136 bytes, merging the two conditional wrap additions
 * and choosing a different register for the final velocity-scale constant.
 */
void
mclib_observer_velocity_update(struct mclib_observer *observer)
{
    float angle = observer->angle;
    float difference = angle - observer->previous_angle;
    if (difference > 0x1.921fb8p+1f)
        difference += -0x1.921fb8p+2f;
    else if (!(difference >= -0x1.921fb8p+1f))
        difference += 0x1.921fb8p+2f;
    observer->previous_angle = angle;
    float velocity = difference * 20000.0f;
    observer->angular_velocity = velocity;
    float filter_delta = (velocity - observer->filtered_angular_velocity) * 0.1f;
    float filtered = observer->filtered_angular_velocity + filter_delta;
    observer->filtered_angular_velocity = filtered;
    observer->scaled_velocity = filtered * 0x1.8723a0p-3f;
}

#endif
