#ifndef GD_ARM_MATH_INTRINSICS_H
#define GD_ARM_MATH_INTRINSICS_H

/* Architectural SDK compatibility, not an assembly replacement for C math.
 * Local AC6.16 include/math.h:414..435 implements __sqrtf/_sqrtf with this
 * always-inline, volatile single-VSQRT form and documents IEEE exceptions
 * instead of errno. Header SHA256:
 * 338e79760f692a96d5a3543e37706c6374d9782a3f46ad5a910d49dd8458cd50
 *
 * The +w operand leaves register allocation to the compiler. Volatility
 * prevents speculative execution outside the caller's C condition, preserving
 * the observed FPSCR behavior. No control flow, fixed register, extra memory
 * clobber or executable payload is supplied here. Stock's use of this exact
 * application-level SDK spelling remains an inference; its gated VSQRT is
 * observed at flash 0x08002e02.
 */
__attribute__((__always_inline__)) static float
gd_arm_sqrtf(float value)
{
    __asm__ __volatile__("vsqrt.f32 %0, %0" : "+w"(value));
    return value;
}

#endif
