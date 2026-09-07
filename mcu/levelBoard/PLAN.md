# The levelBoard rebuild: finished, with one reservation

Upstream Klipper `6d70050` plus the one recovery commit in `klipper/`
reproduces `mcu/levelBoard/stock/levelBoard.bin` exactly. Measured on
2026-09-07 from `klipper/`:

| gate | result |
|---|---|
| `md5sum` ours / stock | `156366b40ccc51f5768e083fa8ead210` both |
| size | 26,704 B both |
| `cmp -l out/klipper.bin levelBoard.bin \| wc -l` | 0 |
| `relocmap.py --all --limit 0` | 247 functions, `EXACT-AT-ADDR 247`, `CODE-DIFF 0`, 7,093/7,093 instructions (100.0 %) |
| `cmpfuncs.py` | `SAME 54  DIFF 0  NOSYM 0` |
| `compare-dict.py` | dictionary matches the stock firmware |
| `compare-blob.py` | 2,281-byte identify blob matches the stock firmware |

| function | address | positional | LCS | bytes |
|---|---|---:|---:|---:|
| `gpio_out_reset` | 0x08007FC0 | 51/51 EXACT | 51/51 | 136/136 |
| `ff_eddy_rebaseline` | 0x08007BF4 | 44/44 EXACT | 44/44 | 164/164 |
| `ff_eddy_update` | 0x080078EC | 275/275 EXACT | 275/275 | 776/776 |
| `ff_eddy_check_trigger` | 0x08007C98 | 101/101 EXACT | 101/101 | 264/264 |
| `DMA_Init` | 0x08008F6C | 64/64 EXACT | 64/64 | 146/146 |

Re-measured 2026-09-07 after the N32G45x peripheral driver was split into
its six SDK modules and all 33 `no_reorder` attributes removed: every row
above unchanged, image still 0 differing bytes. `DMA_Init` now lives in
`lib/n32g45x/n32g45x_dma.c`.

Verified two ways. In the committed tree -- `test/verify.sh` refuses to
run against uncommitted edits, so its pass is a statement about what is
committed -- and the long way round, by lifting the recovery commit onto a
separate clone of upstream at `6d70050` with `git am` and building there:
same MD5, zero differing bytes.  The baseline commit's tree hashes to
upstream's own tree object, so there is no third thing to keep in sync.
The tree and the deliverable are the same object.

The target is stable across releases: the 1.9.4 levelBoard image differs
from 1.9.7 in three bytes, one `movw` inside `get_mcu_version`
(0x08004CAC), which loads 1001 where 1.9.7 loads 7091. Everything else
is identical.

## The open question: six dead conditionals

The tree contains six conditionals with identical arms. Each emits
nothing and exists only to change how often a value is referenced, and so
which register it gets: four in `ff_eddy_check_trigger`, one in
`ff_eddy_update`, one in `DMA_Init`. `gpio_out_reset` and
`ff_eddy_rebaseline` needed none.

One such construct is a believable engineer's slip. Six is not, and the
distribution is lopsided. **The patch reproduces stock's bytes without
being stock's source.** The likeliest explanation is that real code we
have not recovered supplies those references as a side effect, and each
conditional stands in for part of it. Two candidates are under
investigation and this is open:

- the three write-only globals `ff_eddy_last_dev` (0x20000134),
  `ff_eddy_dbg_baseline` (0x20000138) and `ff_eddy_offset`
  (0x2000019C), which look like the residue of telemetry or debug
  statements;
- the `value - 1 > 0xfffe` range-check idiom, which is not how the
  constant would be written by hand.

What is pinned in every case is the class of construct and the cost
threshold it sits on, not the text. `src/ff_eddy.c` carries the caveat
as a comment above `ff_eddy_check_trigger`.

Two measurements sharpen the question, both on that function:

- The hysteresis-tail conditional is not a register lever alone.
  Dropping it and leaving a plain `ff_eddy_trig_count = 0;` gives 103
  instructions and 268 bytes where stock has 101 and 264 (`nm -S`:
  `0000010c`), and takes the image to 26,720 bytes with 10,366
  differing. A four-byte size change is not something a register choice
  can do, so that conditional stands in for a code shape.
- Stock's two range checks use opposite register pairs: the hard arm at
  `0x08007CB6` is `subs r3, r5, #1` then `movw r2, #0xfffe`, the main
  arm at `0x08007CD0` is `subs r2, r5, #1` then `movw r3, #0xfffe`. One
  source shape written twice produces the main arm's form in both, and
  the hard arm's dead conditional is what swaps it. So stock's hard arm
  contains something that has not been reconstructed.

## How the last two closed

### `ff_eddy_check_trigger`, 78/101 to exact

Four dead conditionals: `if (value == 1)` around the hard arm's
pin-state store; `if (value - 1 >= 0xfffe)` around the hard arm's two
counter stores; `if (value == (uint32_t)thr)` around the peel store; and
`if (value == baseline)` around the hysteresis tail's `trig_count`
store.

The mechanism corrects the theory this file previously carried. IRA
drops r0-r3 from an allocno's profitable hard-register set once the cost
of preserving it across `bl irq_enable` exceeds that allocno's memory
cost, and that memory cost is its own frequency-weighted reference
count. So the lever is how often each local is referenced and in which
block, not how long it lives. `thr` being hard to colour and handled
late was a symptom, not the cause. The caller-save cost is bracketed by
measurement to between 9950 and 10470, with one reference in the hot
post-range-check block worth 3300.

Two constraints on the construct. The condition must not be foldable:
`value - 1 > 0xfffe`, the same test as the guard above it, is proved
false by value-range propagation and deleted. And the store a
conditional wraps must be volatile, or GIMPLE tail-merge removes the
conditional before IRA sees it.

### `DMA_Init`, 21/64 to exact

Three changes together, none sufficient alone:

1. the nine field locals become `int` rather than `uint32_t`.
   Signedness is what matters: the signed intermediate keeps its own
   conversion in the tree and that reorders IRA's allocnos. Plain
   `unsigned int` scores far worse;
2. each field is read one group ahead of its use, anchored after the
   previous field's OR rather than before the previous clear;
3. one dead conditional around the `TXNUM` store.

Together they produce stock's two-register save set and three fields in
flight, where ours had three registers and four fields.

Also established: the field loads are not hoisted in GIMPLE. The motion
is sched1, permitted by struct-path aliasing between the parameter
struct and the volatile channel registers. And the whole space of read
placements, without the other two changes, tops out at 140 of 146 bytes
over roughly 84,000 measured candidates.

## Method worth keeping

- The permuter's alignment-tolerant score rewards a candidate that grows
  a function, which is wrong for a fixed-size function like `DMA_Init`.
  That search was driven off a direct byte compare against stock
  instead, with the permuter used only as a source of transformation
  ideas.
- The settings key is `[weight_overrides]`. A `[weights]` table is
  silently ignored, which is how several earlier rounds ran with
  `perm_var_cond_block` disabled while appearing tuned.
- A dead conditional is only visible to IRA if GCC cannot fold it and
  cannot tail-merge it: not provably constant, both arms textually
  identical, and the store it wraps volatile.

## Ruled out (do not retry)

Everything under "Source-shaping experiments ruled out" and "Compiler
flags settled" in `README.md`: any `-f`/`-m`/`--param` switch, fixed
registers other than r10, toolchain versions other than 10.3-2021.10,
LTO, `-Os`/`-O3`, `memcpy()` in the median helper, `uint8_t` selector
fields in `TIM_InitTimeBase`, `barrier()` between the store groups of
`ff_eddy_rebaseline`, `volatile` on all of that function's store
targets, and any `ff_eddy_rebaseline` store order other than the one in
the tree.

For `ff_eddy_check_trigger`: different expressions for the two range
checks (GIMPLE folds both to the same form), and specifically
`value == 0 || value > 0xffff` and `value - 1 >= 0xffff`; the absolute
deviation written as a subtraction, in every order of operands, which
reaches `sub` and never stock's `neg`; nesting the hard arm rather than
returning early, and reordering its two counter stores; a fresh local
copy in the hard path (coalesced), `else` spellings of the hard arm, a
shared `irq_enable()` plus check (the threader duplicates it), reading
`hard` first, barriers, unsigned magnitude (GCC rewrites the negative
arm to `baseline - value` and emits `sublt` where stock has `neglt`),
`__builtin_abs`, unsigned-long `value`/`baseline`, widened `state`
reused as `baseline`, hard-branch probability hints. Context is not the
variable: the upstream `strip_other_fns.py` reduction, a 76-line
reduction, and all 32 static/external linkage combinations of the five
private globals reproduce the reference object exactly.

For `DMA_Init`: `tmpregister` forms (10/63), a local `no-schedule-insns`
attribute (5/63 and a larger image), raw `uint32_t *` parameter indexing
(2/63), `Direction` read into a local at entry (8/63), parameter first
in each explicit OR (no change), all eight configuration fields cached
before their clears (18/64, 57/146 bytes).

## What is next

The other three boards. `README.md` has their table; the skill file
`.claude/skills/mcu-recovery/SKILL.md` has what the levelBoard job
teaches about them.
