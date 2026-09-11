# Compiler alignment and four newly integrated bodies

Measured on 2026-09-09 with the retained, licence-free ATfE 22.1.0 compiler.
Its executable SHA256 is
`6df1642d4dbf2543f33966344207c34e7d6cb36cd8ef67ec4bd2a73342a74349`,
identical to the supplied temporary installation. The four original C probes
still match all 126 bytes, including their pools. These observations do not
identify stock's original compiler release or prove complete-image equality.

## A global alignment hypothesis

The previous configuration requested eight-byte function alignment even for
small, loop-free C runtime helpers. At fixed stock addresses the linker then
inserted leading padding and shifted the actual function symbols. Merely
passing `-falign-functions=2` did not change those input sections.

The backend option `-mllvm -align-all-functions=1` uses log2 alignment: one
means two bytes. Applied globally, it preserves every byte in all 539 sections
of the preceding partial build, including all 175 exact C functions, runtime
assembly, data, vectors and veneers. Literal pools and loop alignment still
impose their own stronger section requirements; the two C scatter-handler
references therefore retain two bytes of leading alignment. They are not
active implementations or C-coverage contributions.

The global diagnostic is retained at `/tmp/gd-partial-forcealign2`; its
comparison baseline is `/tmp/gd-slot-repeat.kyBhuE`. The common flag is now
present in the partial linker, generic gate, regression wrapper and the
standalone GPIO/serial/state defaults. No input section is manually realigned,
no function gets a private option, and no emitted instruction is patched.
This is a compatible measured configuration, not a recovered original command.

| Body | Stock address / span | Candidate span | Status |
|---|---|---:|---|
| `memset` C wrapper | `0x08000446`, 18 B | 18 B | newly integrated, 14 matching bytes |
| `gpio_out_reset` | ITCM `0x31b0`, 264 B | 196 B | newly integrated, unmatched |
| `gpio_out_toggle_noirq` | ITCM `0x3320`, 266 B | 112 B | newly integrated, unmatched |
| `mclib_sincos` | `0x08002970`, 480 B | 452 B | newly integrated, unmatched |
| `mclib_sqrt_positive` | `0x08002df8`, 28 B | 28 B | exact C with SDK architectural intrinsic |
| `SystemInit` | `0x08000620`, 548 B | 548 B | 546 matching bytes |

The GPIO source makes immutable, by-value pin-tag alternatives an `else if`
chain. It does not remove physical GPIO accesses for motor pseudo-pins, change
the short-circuit inhibitor reads, or change the motor-call arguments/order.
The stock's redundant post-call checks are not reproduced. All 10,156 modeled
ABI/MMIO cases pass, but these smaller bodies remain instruction mismatches.
Input setup, output setup and output write compiled sections are unchanged.

The sine/cosine source exposes the shared address of complementary cosine
samples as `&mclib_sine_table[128-index]`, with offsets one and zero. This
reduces repeated integer address calculations without changing the per-result
FP formulas. Both results precede the sine-then-cosine stores, including the
aliased-output case. The separate sine body is unchanged, and the compiled
131-float table remains 524/524 exact bytes.

`check-gd-trig-model.py` validates 34,816 finite output-bit, ordered-write,
FPSCR and ABI cases across all 16 rounding/FZ/DN combinations and distinct or
aliased pointers. Eight NaN/infinity/huge-input checks observe no output or
return within 10,000 instructions; this is not an infinite-execution proof.
The model does not validate standalone `mclib_sine`, physical timing, or the
order of independent table reads/FP operations.

The final clock-status field in `SystemInit` takes only masked values
0, 4, 8 or 12. Testing `<=8` preserves its single-read polling semantics and
retains stock's AND instruction. Two bytes remain different: candidate
`CMP #9; BLO` versus stock `CMP #12; BNE`. All four MMIO traces still match.

## Recovering the actual hardware square-root abstraction

The generic elementwise square-root builtin speculated VSQRT before the
positivity test. For negative inputs it returned the correct positive zero
but incorrectly added FPSCR.IOC. This was a real semantic difference.
`FENV_ACCESS` is unsupported for this compiler target, and selecting a
nonnegative input in C was optimized back into the same speculative form.

The local original AC6.16 `include/math.h`, lines 414–435, provides a different
abstraction: `__sqrtf`/`_sqrtf` is an always-inline, volatile VSQRT instruction
with a read/write floating-point operand. Its documentation explicitly
distinguishes IEEE exceptions from the standard library's errno semantics.
That header has SHA256
`338e79760f692a96d5a3543e37706c6374d9782a3f46ad5a910d49dd8458cd50`.

`arm_math_intrinsics.h` retains this narrowly scoped architectural interface.
Register choice is left to the compiler; it supplies no branch, fixed register,
memory clobber, opcode payload, or replacement business-logic body. The
positivity test and both returns remain C. The function and its zero literal
now match all 28 stock bytes. The application's original SDK spelling remains
an inference, not a source-provenance claim or permission to translate other
unmatched arithmetic into assembly.

`check-gd-sqrt-model.py` separately compares output bits, FPSCR and preserved
ABI state over 16,672 cases. The DQ limiter's 41,984-case model still executes
the actual stock square-root callee; the reconstructed helper has its own
independent exact-byte/model evidence. The other three math sections did not
change when the shim was introduced.

## Remaining runtime integration exclusions

Five C bodies are still too large. All now enter at their actual stock
addresses, so these are instruction-size gaps, not hidden leading padding:

| Body | Candidate / stock bytes |
|---|---:|
| `__aeabi_memmove` | 78 / 64 |
| `__aeabi_memset` | 18 / 14 |
| `__aeabi_memclr` | 6 / 4 |
| `memchr` | 22 / 20 |
| `gd_runtime_decompress` | 128 / 94 |

The original library metadata identifies these as C sources, unlike the
already-recovered assembly-origin scatter copy/zero handlers. They must not
be replaced with copied library instructions to score a source match.

ADC setup remains 219/220 bytes: only CMP's operand order differs, feeding an
equality branch before the flags are overwritten. Signed and byte channel
types regress the candidate to 217 matching bytes; pointer iteration leaves
it unchanged. No experiment was adopted. Existing ADC vendor/IRQ models do
not cover setup's calibration polling path.

The final regression passes 32/64 gate processes; the other 32 report expected
byte mismatches. All 456 independent integration-parity sections pass. The
partial link contains 176/281 exact C bodies (10,052 complete-span bytes),
105 integrated mismatches and the five exclusions above. All 175 previously
exact C functions remain exact. Of the previously integrated sections, only
`SystemInit` and square root changed; four additional C bodies are now linked.

The canonical ELF and initialized-RAM output are byte-identical to an
independent build at `/tmp/gd-alignment-repeat-final`. Initialized RAM remains
11,912/11,912 exact bytes and the separate scatter artifact 3,284/3,284. The
inventory has 45 fresh canonical reports, no conflicting evidence, and a
27,684-byte unique runtime-address union excluding ZI; 236 of those bytes
remain separately classified runtime assembly. The gap audit still classifies
all 2,686 apparent code-gap bytes. LevelBoard's binary still matches stock and
its tracked source is unchanged.

The [current plan](../PLAN.md) records remaining work. A fitting partial link,
bounded execution model or collection
of exact functions is still not a flashable or byte-identical firmware image.
