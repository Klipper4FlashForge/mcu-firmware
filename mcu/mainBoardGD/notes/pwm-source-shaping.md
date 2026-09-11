# PWM initialization source-shape follow-up

This pass targets `mclib_pwm_channel_init` at `0x3c20` (98 bytes) and
`mclib_pwm_init` at `0x3c88` (116 bytes) in
`recovered/mclib_pwm_vendor.c`. The initial candidates matched 89/98 and
93/116 bytes. All seven already-exact PWM functions, totaling 230 bytes,
are regression gates. The shared compiler flags remain unchanged.

## Stock evidence and shaped trials

After the OC-defaults call, stock clears the final parameter word first
at `0x3c32`, then the first two words using `STRD` at `0x3c34`.
The initial candidate uses three separate word stores. In the public
initializer, stock loads `half_period_ticks` separately at `0x3c9c`,
stores auxiliary period and period separately, and loads the timer
address at `0x3cb2`. The candidate instead combines the state loads and
some parameter stores with `LDRD`/`STRD`.

Three scratch hypotheses preserved every existing PWM exact:

| Hypothesis | Channel | Initializer |
|---|---:|---:|
| OC idle-pair first; auxiliary period before period | 90/98 | 86/116 |
| Same, with an explicit precomputed period temporary | 90/98 | 86/116 |
| OC aggregate zero initialization; auxiliary before period | 89/98 | 86/116 |

All emitted extents remain unchanged. The initializer variants above
were rejected as regressions; a better parameter-store order was sought
with bounded source permutation instead.

## Raw-byte search and semantic review

Two targets use the complete 98/116-byte extents at their original Thumb
entries, with every SDK dependency resolved to its observed address.
Minimal typed C inputs reproduce the canonical full function bytes
before searching. The objective counts positional byte differences,
including missing/extra bytes and entry/symbol penalties; it does not
normalize instructions or ignore pools. Baseline self-tests yield 9 and
23 differing bytes, while both stock comparison targets score zero.

The search is capped at 20,000 seed tasks **per target**, four workers
total. It was staggered after the motor agent's search rather than
running eight workers. Every distinct emitted-byte improvement below
baseline is retained. Compiler flags, ABI and declarations stay fixed;
no instruction blobs, assembly, register pinning or per-function options
are used. Transformation weights are recorded in each target's
`settings.toml`; dedicated type mutation and deletion/dummy-arithmetic
passes are disabled. Temporary creation can still introduce narrowing
types, so emitted source requires semantic review.

The simple eligible candidates move only local parameter assignments:

- `output_idle = 0` before the other OC fields gives **90/98** bytes.
- `direction = 0` before prescaler/alignment gives **99/116** bytes.

The run completed **40,000 iterations (20,000 per target)** in 524.97
seconds, with 1,107 compile-error iterations and zero internal errors.
There were 38,893 non-error iterations, which are not necessarily unique
compiled programs. Thirteen distinct improving outputs were retained
and independently recompiled for full-byte/size/entry audit. None was
byte-exact. Session 55804 exited cleanly and all four workers were freed.

The two simple changes above were adopted into the canonical C only
after that search and semantic review. The canonical PWM gate confirms
their seven-byte combined gain, unchanged extents, all eight non-target
sections byte-identical, and seven previously exact functions preserved.
Its overall exit status remains nonzero because three functions are not
exact; a partial improvement is not reported as a passing equality gate.

Both keep the complete SDK call order, full-width timer address,
parameter values and padding behavior. Combined in the full C module,
they preserve all seven exact functions and pass all **982** existing
ordered MMIO/call/configuration model cases. The model executes the
stock defaults helpers but mocks other SDK callees; it does not prove
motor hardware operation, interrupt interleavings or a complete boot.

The tempting 104/116 candidates are rejected: they narrow `pwm->timer`
through an eight- or sixteen-bit temporary before `gd_motor_timer_init`,
discarding the peripheral address high bits. Another 95/116 candidate
has the same flaw. A better byte count does not justify changed meaning.

Even the eligible candidates are **not byte-exact**. Channel setup still
lacks stock's paired store; the initializer still has different paired
loads/stores and scheduling. This is a reduction in actual differing
bytes, not completion of either function or merely fitting a smaller
candidate into the stock slot.

## Retained records

Scratch artifacts are in `/tmp/gd-pwm-shape.PDFr6t/`: three hand trials,
two isolated permuter targets, fixed compiler/link inputs, complete-byte
audits, semantic review, progress/logs and the combined model source and
result. The summary captures input/compiler/source and permuter-module
hashes. This temporary directory is not a durable build deliverable.
The random search is finite, not exhaustive or exact-seed replayable;
non-error iteration counts can include cached candidates.

Fresh canonical results are `work/mainBoardGD-pwm-vendor/results.json`
and `work/mainBoardGD-pwm-vendor-model.json`; the post-adoption model
also passes 982/982 cases. Adopted C SHA-256 is
`6eb27683b668e5b9b2fc501af8d4b2fbde8fd50b1bfbec660edd4171e8a4aded`.
Scratch summary SHA-256 is
`f2857d30e8f4851445cf36405b51d897c244dbeed2a2c65f7f3060f04f760c7e`.
