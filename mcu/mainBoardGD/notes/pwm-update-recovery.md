# PWM update source-shape recovery

The complete stock `mclib_pwm_update` spans ITCM `0x3b38..0x3c1c`, 228 bytes,
including its 7500.0f and 15000.0f literal words. The next helper starts at
`0x3c20`, after four alignment bytes. Both control loops reach this function
through the flash veneer at `0x080031b6`.

The adopted source improves from **77/228 matching bytes, candidate 224 bytes,
to 95/228 matching bytes, candidate 228 bytes**. Its full symbol and section
have the correct entry and extent; it is still nonexact. All other 31 motor
sections remain unchanged, including the exact PI body. The motor gate stays
23/32 exact functions, totaling 1,240 complete-span bytes.

## Stock behavior and constraints

The pattern polarity byte is loaded once from offset 2. Alpha and beta primary
fractions are at offsets 4 and 16; their extensions are at offsets 8 and 20.
Each primary generates positive/negative tick counts by adding/subtracting
1.0f, multiplying by 7500.0f and converting to unsigned integer. The positive
integer is converted back to float before a fused multiply-add of extension
times 15000.0f. These conversions and both VFMA instructions are essential;
neither a float-only expression nor split multiply/add is interchangeable.

Each bridge performs four ordered 32-bit MMIO writes. The exact offset order is
`0x34, 0x64, 0x38, 0x68, 0x3c, 0x6c, 0x40, 0x70`. Polarity bits 0 and 1
select which count goes to each register; higher bits are ignored. Stock
reloads the timer peripheral address from the state object before every write,
including the last write at `0x3c0e..0x3c10`. No range guard or clipping exists.
Invalid/out-of-range C float-to-uint conversions remain compiler/target-specific;
the model compares the actual emitted VCVT behavior, not portable C semantics.

The retained source gives the final beta-extension register a named volatile
pointer immediately before its write. The pointer is resolved only after the
preceding bridge writes, not cached across them. Both VFMA operations, all
eight state-pointer reads and all eight MMIO writes are preserved. The compiler
chooses separate beta-branch epilogues and moves the literal pool to its stock
offset. This is a measured byte improvement, not evidence of the original C
spelling or a solved function. Floating scheduling, registers and branch-tail
sharing still differ.

## Three hypotheses and raw-byte search

Scratch work is retained at `/tmp/gd-pwm-shapes.IjN8GY`.

| Source hypothesis | Candidate bytes | Matching bytes |
|---|---:|---:|
| Baseline | 224 | 77/228 |
| Local volatile views of extension loads | 224 | 68/228 |
| Local volatile views of all four pattern floats, each sampled once | 224 | 71/228 |
| Explicit primary and sum/difference temporaries | 224 | 77/228 |

None of those three hand shapes is adopted. A minimal source baseline was
compiled independently and verified to emit all 224 canonical bytes before
the subsequent permutation run. The same global compiler flags are used;
no flags, fixed registers, assembly or literal opcode arrays are candidates.

The four-worker search completes 20,000 iterations in 200.77 seconds, with
4,351 compile errors and zero internal errors. Its objective checks every
positioned byte, complete section length, symbol size and actual section,
Thumb-symbol and ELF entry addresses. Length/entry self-tests reject growth,
truncation and shifted symbols. The initial score is 151 differing/missing
bytes; best raw score 102 is not a valid recovery result.

All 287 distinct saved outputs are independently rebuilt and audited. Sixteen
are oversized; another 261 fail bounded instruction-model checks. Ten pass
the 124-case smoke screen and are then read as C. Eight of those are rejected
for tick-count narrowing to `short` or splitting/moving the fused extension
calculation. The two credible remaining spellings score 79/228 and 95/228;
only the stronger, named-register-pointer version is adopted after the full
model and full motor gate.

Important rejected examples:

- The best 126/228-byte candidate converts `beta_primary` to unsigned integer
  before computing its timing fraction. This destroys fractional input.
- Some candidates exchange MMIO writes, cache the timer pointer across writes,
  introduce extra timer-pointer reads, or narrow the timer address itself.
- A `short` tick temporary can pass a small ordinary-value screen but cannot
  preserve a 32-bit timer value. The durable model adds moderate out-of-range
  primary values such as -10, producing 82,500 ticks before any narrowing.
- Separating extension multiplication from addition can remove stock's FMA
  even where ordinary numeric examples happen to agree.

This is a finite random search, not proof that an exact spelling does not
exist. Non-error iterations include cached candidates, and the random seed
stream is not pinned for exact replay. Enabled transformations have the same
limitations as the [atan search](atan-permutation-search.md): dedicated type
mutations are disabled, but temporary creation can still change types.

## Reproducible model

```sh
python3 tools/check-gd-pwm-update-model.py
```

The gate validates the canonical motor report's source/header/compiler/stock
hashes, actual ELF section and Thumb entries, full function/pool extent and
candidate bytes. It executes actual stock and candidate ARM instructions in
Unicorn, with no mocked calls, conversions or floating-point operations.

The initial 30,720 cases pass for both the old and adopted candidates. The
durable suite adds finite conversion-boundary examples; all 32,256 cases pass:
four rounding modes crossed with FZ/DN, signed zeros, subnormal boundaries,
finite extrema, infinities, quiet/signaling NaN payload pairs, random full-bit
float patterns and all 256 polarity bytes. It compares every ordered MMIO
write, all state read counts, complete timer storage, unchanged PWM/pattern
objects, final FPSCR, preserved r4-r11/d8-d15, SP and return PC. It requires
exactly eight timer-address reads and the specified eight write offsets.
Mapped accesses, execution boundaries and stack canaries are guarded.

The model uses ordinary register latches. It does not validate real PWM
waveforms, asynchronous state changes, aliased parameter objects, full load
scheduling, physical FP exception timing or complete loop/firmware behavior.
The result and content-based provenance are saved as
`work/mainBoardGD-pwm-update-model.json`. Exact-function totals do not increase
in this batch; whole-image equality remains unproved.
