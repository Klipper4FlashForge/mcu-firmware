# Statistics: complete 232-byte C match

The unchanged shared ATfE 22.1.0 configuration now reproduces `stats_update`
at ITCM `0x46c8..0x47b0` exactly: **232/232 bytes**. This includes 198 code
bytes through `0x478e`, two bytes of alignment, and the 32-byte inline
message-string/padding span at `0x4790`. Entry, Thumb symbol and full symbol
size are checked; this is not an instruction-normalized or prefix result.

## Missing read and source lifetime

The previous 228-byte candidate matches 67/232 positioned bytes. Stock reads
`stats_sumsq` in either selected arithmetic branch (`0x4708` or `0x471c`),
then **reloads** it at `0x472a` for the saturation comparison. The prior C
forwards the first value into the comparison, so the second load is absent.
For a large elapsed difference, stock skips the arithmetic read but still
performs the final saturation read.

The adopted source uses a local volatile word view only for that final read.
It does not widen a global, add a lock, alter the state layout, or replace
the arithmetic with assembly. This restores the observed access and most
of the original register allocation.

Stock also snapshots `stats_send_time` at `0x473c`, retains it across the
real `timer_from_us` call at `0x4748`, and subtracts it from `now` at `0x474c`.
Explicit `previous_send_time` and `period` locals retain that source lifetime.
Finally, spelling the later wrap test as `stats_send_time > now` selects
stock's `CMP r0,r4`/`BLS` rather than the complementary operand order and
condition. The global is still reloaded after sending, at `0x4766`; the
earlier snapshot is not reused for this check.

| Source trial | Candidate bytes | Matching bytes |
|---|---:|---:|
| Baseline | 228 | 67/232 |
| Explicit accumulator reload | 232 | 222/232 |
| Reload plus pre-call timestamp/period locals | 232 | 230/232 |
| Reload plus reversed wrap-comparison operands | 232 | 224/232 |
| Reload plus an unnecessary volatile final timestamp read | 232 | 222/232 |
| Reload, timestamp/period locals and reversed comparison | 232 | **232/232** |

The three necessary changes are adopted in `recovered/statistics.c`; the
additional volatile timestamp view is not retained. Scratch sources and
complete linked artifacts are in `/tmp/gd-base-next.t6Q6vv/`. An independent
reviewer recompiles the canonical source into `/tmp/gd-stats-review.9hrh5thz/`
and confirms the same full-span SHA-256:
`bd04a4303fcde3c923232d10fd6ff08e4aab206dc4f66bec1629b6bbc3321a43`.
No source-permutation search is needed to close this function.

All subtraction, multiplication and accumulation remain unsigned 32-bit
operations with the observed wrapping and saturation. The two unsigned
comparison spellings are equivalent over the complete input domain. The
new read is grounded in the actual instruction, not inferred solely from
a better byte score. This is valid matching C, not proof that the original
author used this volatile spelling or that the statistics state is safe
under concurrent access.

The statistics-only full base gate improves from **39/45 exact, 2,296 bytes**
to **40/45 exact, 2,528 bytes**. All 44 other base section hashes, including
the newly recovered queue insertion and all previous exact functions, are
unchanged. The final combined scoreboard may include subsequent work.

## Durable execution and provenance checks

```sh
python3 tools/check-gd-base.py
python3 tools/check-gd-stats-model.py --self-test
python3 tools/check-gd-stats-model.py
```

The model passes **1,564 deterministic cases** and **13 negative provenance,
entry, extent and candidate-byte tests**. The input set crosses arithmetic
branch boundaries, unsigned timer wrap and the three-billion-tick reporting
threshold, then adds random full-word state and arguments. Counts, sums and
the high timer word may wrap. An independent unsigned arithmetic/state
oracle checks the complete five-word statistics state and combined ordered
state-read/write/call trace, including values and access widths.

The eight actual stock `timer_from_us` bytes execute directly, computing
5,000,000 times 600 modulo 2^32. Encoder lookup and sending are explicitly
mocked and clobber caller-saved data registers. Selected cases change the
accumulator at its final read or statistics state at the send boundary to
exercise the required reloads. These are prescribed dependency behaviors,
not a simulation of interrupt timing or a concurrency-safety proof.

The checker pins source/header, compiler, stock, ELF and checker hashes;
guards mapped accesses and stack/object boundaries; and checks preserved
r4-r11, SP and return PC. The report is
`work/mainBoardGD-stats-model.json`. The new model is wired into the common
recovery wrapper. Finite model coverage and this exact function do not
establish complete scheduler behavior, hardware timing, bootability or
whole-image equality.
