# levelBoard recovery log

The long-form record behind `../README.md`: what had to be pinned, which
compiler behaviours decided layout, what was ruled out and why. Cited by
stock address throughout. `../PLAN.md` carries the one open question.

threshold it sits on, not the text. `src/ff_eddy.c` carries the caveat
as a comment above `ff_eddy_check_trigger`, and two measurements sharpen
it. Dropping that function's hysteresis-tail conditional gives 103
instructions and 268 bytes where stock has 101 and 264, and takes the
image to 26,720 bytes with 10,366 differing -- a size change no register
choice can produce, so the conditional stands in for a code shape. And
stock's two range checks use opposite register pairs (`subs r3, r5, #1`
then `movw r2, #0xfffe` in the hard arm at `0x08007CB6`, the reverse in
the main arm at `0x08007CD0`), where one source shape written twice
gives the main arm's form both times; stock's hard arm therefore holds
something not reconstructed.

The instruction comparator retains data immediates and normalises only
control-flow targets and pc-relative literal offsets, so the matches do
not hide differing constants.

**Things that turned out to be link-level, not code.** Most of the last
few thousand differing bytes were not instructions at all:

- `.bss` is in an order that is neither link order nor alphabetical:
  `sched.c`'s `shutdown_jmp` sits between the eddy sensor's wake flag and
  its timer, and `ff_shutdown_code` between the tmcuart and trsync wake
  flags. `-fdata-sections` gives every variable its own `.bss.<name>`
  section, so the linker script simply lists them in stock's order.
- `.data` ends with `SystemCoreClock` at `0x20000040`, after the eddy
  sensor's initialised variables.
- one `.ARM.exidx` entry (8 bytes, `EXIDX_CANTUNWIND` for `__udivmoddi4`)
  sits between `.rodata` and `.init_array`, and crtbegin's empty
  `.eh_frame` sits ahead of `.init`, which is where its literal pools
  point.
- the stack is 2 KiB, not Klipper's 512 B default: `dynmem_end` is
  `0x20003800`.
- the PendSV slot of the vector table points at `DefaultHandler` while the
  other unused system exceptions stay null.
- the `command_parametersN` tables are numbered by first appearance of a
  parameter-type tuple while the response encoders are emitted, which is
  descending source line of the declarations; `identify_response` has to
  come after the five FlashForge responses.
- two things our reconstruction had subtly wrong and the image settles:
  `endstop_recover_state` calls `sched_del_timer()` on the endstop's timer
  rather than `irq_disable()`, and `sched_add_timer()` stores the requested
  wake time in the variable the shutdown report calls `Temp_waketime` and
  the current time in `Close_num`.

**Compiler behaviour that decided layout.** Most of the closed functions
hinged on GCC's branch-prediction heuristics rather than on any
instruction-level rewrite:

- `ff_eddy_update`'s whole smoothing path was laid out of line because the
  branch into it guards a call: GCC's *call heuristic* predicts a branch
  to a block that calls a non-pure function as 33 % taken. The median
  helper copied the ring with `memcpy()`, which makes it impure; a plain
  copy loop compiles to the same `ldm`/`stm` bytes but leaves the helper
  pure in GCC's early analysis, and the layout snapped into stock's.
- The rest of `ff_eddy_update` (all 275 instructions and all 776 bytes at
  `0x080078EC`) is in stock's order through twelve spellings in
  `src/ff_eddy.c`, each carrying its comment. The mechanisms:
  - *Return placement.* The gimplifier attaches an early-return
    prediction (66 %) to every explicit `return` that is not the
    function's last statement, and `predict_paths_leading_to` marks the
    edge cut it post-dominates. Where the returns sit therefore sets the
    branch probabilities that decide which global address IRA keeps in
    r9 (`&filter_acc`; stock rematerialises `&have_filter` three times)
    and which trace ends bb-reorder copies the epilogue onto (an edge
    needs at least 10 % of the entry count). The shape is
    `if (!have_filter) { if (ring_count == 11) seed; return; }` with the
    smoothing at function level, `if (!quiet_start_ms) quiet_start_ms =
    now;` with no return, and recalibration falling off the end.
  - *Store sinking.* tree-ssa-sink moves a store whose VDEF's only use is
    the merging PHI when the target block's count is under 75 % + 7 % of
    the source's. `store = baseline; inrange_count++; outrange_count =
    0;` ahead of the drift compare keeps the store and the baseline load
    in the in-range block (stock's `strh; ldr` before the branch, with
    `&baseline` in r6 for the drift path), and `unlikely()` on the ring
    wrap puts the not-wrap edge at 90 % so the `ring_pos` store stays
    unconditional (`strb`, not `it ls; strbls`).
  - *No `ABS_EXPR`.* `uint16_t adev = dev < 0 ? (uint16_t)-dev :
    (uint16_t)dev;` is a PHI of two conversions, which phiopt's
    `abs_replacement` does not match; combine then consumes the
    subtraction's own flags, `subs; it mi; negmi; uxth`, where an
    `ABS_EXPR` gives `sub; cmp #0; it lt; neglt`.
  - *Compare operand order.* forwprop canonicalises a compare by SSA
    version; in the inner sort `uint32_t cur = devs[sj]; if (key >= cur)
    break;` numbers `cur` after `key`, so the compare is key-first.
  - *isqrt.* The classic `r`/`next` loop returns the loop variable
    (stock's `mov r1, r0` / `mov r1, r2`), and `if (unlikely(!v)) return
    0;` keeps the shared join block below the saturating 3*MAD arm in
    bb-reorder's trace order. The guard's early-return prediction is
    inlined into `ff_eddy_update`, where it sets the count of the join
    block shared by the helper's two exits: at the default 34 % that
    block outranks the 3*MAD arm (the round-3 threshold is 50 per mille
    of the entry count), and cold it does not.
  - *Tie-breaks and schedule.* bb-reorder's `better_edge_p` breaks an
    equal-probability tie by which successor is physically next, so
    `if (mad) { saturating 3*mad } else lim = mad_limit;` fixes the arm
    order; the min-then-max clamp schedules `cmp #60; movge` before the
    `add.w ... lsr #2`; sched2 keeps independent plain stores in source
    order, so `ff_eddy_calibrated = 1` directly after
    `ff_eddy_have_filter = 0` gives stock's r0/r1 naming and the
    `movs r1, #1` placement; a signed temporary for the sigma floor
    (`int32_t mad3over2 = mad + mad/2; uint32_t floor_sd = mad3over2;`)
    gives the floor its own SSA name and stock's r1/r2 in the clamp block.
  - *A dead conditional that survives to IRA.* The callee-saved naming
    hung on one thread order: IRA colours by ascending thread frequency,
    the (mad, lim) thread is 58 and `&ring_pos` is 55, and the last
    pushed takes r6. A conditional on `ff_eddy_ring_pos` around the
    `ff_eddy_mad = mad` store, with both arms storing the same value,
    emits nothing -- the arms are cross-jumped after reload and the load
    and compare are then deleted -- but keeps a reference to
    `&ff_eddy_ring_pos` alive into IRA, which lifts that allocno above
    the (mad, lim) thread and gives stock's r6 and r7 across the whole
    function.

    Stock's source contains such a conditional. Its text cannot be
    recovered, because nothing of it survives compilation; what is
    pinned is the class, established by measurement in `exp/bugshape`.
    The condition must read `ring_pos` -- the same construct on
    `ring_count` regresses the image to ~11,254 differing bytes. It must
    be one GCC cannot fold: a ternary with identical arms folds and
    leaves the image at 119. And both arms must be identical: a
    redundant wrap check that assigns gives 10,956, storing and then
    re-storing under `!ring_pos` gives 11,065, comparing `ring_pos`
    against `ring_count` gives 11,254. Both `if (ff_eddy_ring_pos)` and
    `if (ff_eddy_ring_pos >= FF_EDDY_NSAMP)` with identical arms are
    exact, as are a `uint8_t` temporary form and one whose `else` arm
    respells the same value. The likeliest reading is a bounds check
    whose arms were filled in identically by mistake, which would be
    invisible in testing because the ring scrub it sits beside has no
    observable effect either. It is not a claim about what FlashForge
    wrote.

  Each spelling reproduces stock's bytes; where the mechanism is a
  probability threshold or a tie-break, any spelling on the same side of
  it does too, so this is not proof of FlashForge's text.
- `TIM_InitTimeBase` needed three things: `bool` selector fields (a
  `bool` load is not a character access, so it may be scheduled across the
  volatile register stores, where `uint8_t` cannot), the basic-timer path
  as an `else` branch rather than an early return, and the second timer
  compare at even odds -- GCC's pointer heuristic calls a pointer equality
  30 % likely, and stock's compiler evidently did not see one there. The
  tree carries `__builtin_expect_with_probability(..., 0.5)` for that with
  a comment; the spelling FlashForge used is not known.
- `GPIO_InitPeripheral` was closed by deleting an early `return` for an
  empty pin mask that the loop guard already handles.
- `TIM_ETRClockMode2Config` was closed by reading the prescaler parameter
  into a local *before* the register temporaries. GCC numbers SSA names in
  first-use order, orders the operands of a commutative operation by SSA
  version, and the two-operand Thumb `orrs` takes its destination from the
  first operand: the early use is what puts the final `orr` into the
  prescaler's register, r1, instead of r3. First-use order is a lever on
  register choice generally.
- `gpio_out_reset` is exact with upstream's loop over `digital_regs`
  and a separate `bit_to_pin()` helper. The loop's exit probabilities
  reproduce stock's layout and register assignment at `0x08007FC0`.
- `ff_eddy_rebaseline` is exact with `hard_trigger` and `trig_count`
  volatile, `ring_count` reset before `ring_pos`, and the post-interrupt
  stores ordered as trig_acc, untrig_count, trig_count, pin_state,
  hard_trigger, peel, calibrated. GCC's scheduler and register allocator
  reproduce all 164 bytes at `0x08007BF4`; the two open eddy functions
  retain their bytes. Making the accumulator volatile instead regresses
  trigger detection.
- `ff_eddy_check_trigger` is exact at `0x08007C98` through four dead
  conditionals: `if (value == 1)` around the hard arm's pin-state store,
  `if (value - 1 >= 0xfffe)` around the hard arm's two counter stores,
  `if (value == (uint32_t)thr)` around the peel store, and
  `if (value == baseline)` around the hysteresis tail's `trig_count`
  store. The mechanism is a cost threshold, not liveness: IRA drops
  r0-r3 from an allocno's profitable hard-register set once the cost of
  preserving it across `bl irq_enable` exceeds that allocno's memory
  cost, and that memory cost is its own frequency-weighted reference
  count. The lever is therefore how often each local is referenced and
  in which block, not how long it lives; `thr` looking hard to colour
  and being handled late was a symptom. The caller-save cost is
  bracketed by measurement to between 9950 and 10470, with one
  reference in the hot post-range-check block worth 3300. Two
  constraints on the construct: the condition must not be foldable
  (`value - 1 > 0xfffe`, the same test as the guard above it, is proved
  false by value-range propagation and deleted), and the store a
  conditional wraps must be volatile, or GIMPLE tail-merge removes the
  conditional before IRA sees it.
- `DMA_Init` is exact at `0x08008F6C` through three changes together,
  none of which is sufficient alone. The nine field locals are `int`
  rather than `uint32_t`, where signedness is what matters: the signed
  intermediate keeps its own conversion in the tree and that reorders
  IRA's allocnos, while plain `unsigned int` scores far worse. Each
  field is read one group ahead of its use, anchored after the previous
  field's OR rather than before the previous clear. And one dead
  conditional wraps the `TXNUM` store. Together they give stock's
  two-register save set and three fields in flight, where the earlier
  shape had three registers and four fields. The field loads are not
  hoisted in GIMPLE: the motion is sched1, permitted by struct-path
  aliasing between the parameter struct and the volatile channel
  registers. The whole space of read placements, without the other two
  changes, tops out at 140 of 146 bytes over roughly 84,000 measured
  candidates.
- `DMA_GetIntStatus` and `DMA_GetFlagStatus` are the same six instructions
  twice, and stock's second copy has its `tst` operands swapped. That is
  GCC's identical-code folding re-emitting the folded copy; no spelling of
  the body produces it on its own. It also settles which copy each DMA
  handler calls: channel 5 the interrupt pair, channels 1 and 4 the flag
  pair.

**Compiler flags settled by whole-image measurement.** `-fno-shrink-wrap`
and `-ffixed-r10`: stock's compiled C never uses r10, taking r11 where it
needs a seventh callee-saved register and spilling for an eighth. A sweep
of 380 further switches (`flagsweep.sh`: rebuild a tree copy with one
extra flag, score the open functions, check the rest stayed exact) found
nothing: every `-f`/`-m` option, `--param` knob (pending-list length,
pressure algorithm, IRA and scheduler heuristics) and fixed-register
choice either changed nothing or regressed the image as a whole. The
compiler is not the variable any more; the source spelling is.

**Source-shaping experiments ruled out in the September follow-up.**

- Explicit reusable `tmpregister` forms for `DMA_Init` -- compound
  assignments, plain assignments, and tighter local scopes -- all
  canonicalize to the same 10/63 match and `{r4,r5,r6}` save set. A local
  `no-schedule-insns` attribute regresses it to 5/63 and grows the image
  to 26,732 bytes.
- Six natural `gpio_out_reset` variants covering helper argument order,
  explicit temporary declaration order, and aggregate/SRA forms all stay
  at 48/51. Local `rename-registers` falls to 37/51; IRA priority falls to
  20/53.
- Making `ff_eddy_trig_acc`, `hard_trigger`, and `untrig_count` volatile,
  then scalarizing the accumulator and trigger counters, leaves
  `ff_eddy_rebaseline` at 33/44 and drops `ff_eddy_check_trigger` from
  78/101 to 59/101, and costs the image 36 further differing bytes.
- In `ff_eddy_update`: `volatile` on `ring_pos`/`ring_count` breaks
  `ff_eddy_rebaseline`; `ff_eddy_mad` without `volatile` takes the image
  to ~3,552 differing bytes; the ring wrap without `unlikely()` to ~545;
  `likely(have_filter)`, `unlikely(!sample_ready)`, moving the volatile
  `sample_ready` store, and unsigned `dev` with a signed cast test
  (combine folds it to `submi`) all regress or do nothing. For the
  callee-saved rename the dead conditional finally closed: every
  scrub-loop shape, `!mad` first, reusing `mad` as the limit, expect
  hints on `if (mad)`, `if (ring_count)` and the loop, comparing
  `devs[5]` directly (one byte worse), recalibration without
  its early return (same bytes). Manual `PERM_GENERAL` mode over the
  ring tail and the mad/lim expressions is code-neutral throughout, so
  those spellings are dead ends.

None of these is in the tree.

On `ff_eddy_check_trigger`, context is not the variable and arithmetic
was not either. The upstream permuter's context-isolation tool, a
further 76-line reduction and all 32 static/external linkage
combinations of the function's five private globals each reproduce the
reference object exactly, and so does replacing the assembly home-reset
with equivalent C. An unsigned-magnitude arithmetic shape reaches
243/264 bytes but emits `sublt` where stock has `neglt`, and 20,001
trials from it rediscover only the reference code. What closed the
function was the reference-count lever above.

Two things about the permuter itself. Its alignment-tolerant score
rewards a candidate that grows a function, which is wrong for a
fixed-size function like `DMA_Init`; that search was driven off a direct
byte compare against stock instead, with the permuter used only as a
source of transformation ideas. And the settings key is
`[weight_overrides]` -- a `[weights]` table is silently ignored, which
is how several earlier rounds ran with `perm_var_cond_block` disabled
while appearing tuned.

**The toolchain is settled, and it was settled by libgcc.** `__udivmoddi4`
is prebuilt: no source edit and no `-f` flag can change it, so if it does
not match stock, the toolchain is wrong -- and that can be tested without
building the firmware at all, by scoring each libgcc multilib in the
toolchain against the stock image:

| multilib | `__udivmoddi4` vs stock |
|---|---|
| `thumb/v7e-m+fp/softfp` | 250/250 (100 %) |
| `thumb/v7e-m/nofp` | 39/248 (16 %) |
| `thumb/v7-m/nofp` | 29/251 (12 %) |

Stock links the FPU multilib. **The N32G45x is a Cortex-M4F and we had been
building it as a Cortex-M3** -- the tree reconstructs the part from
Klipper's STM32F103 headers, which pull in CMSIS `core_cm3.h`, and that
header refuses to compile the moment VFP instructions appear. With
`-mfpu=fpv4-sp-d16 -mfloat-abi=softfp` and `core_cm4.h`, handlers went from
41 to 49 and `__udivmoddi4` became **250 of 250 exact**. GCC 10.3-2021.10 is
confirmed correct; no version hunt is needed.

**Layout facts that hold.** The objects are linked in stock's own order
(reproduced by the Makefile's explicit tail list), `.text` starts at
0x08004120 aligned to 16 with zero fill, plain `.text` input sections
(crtbegin, libgcc, libc's assembler) precede the function-sectioned ones,
and `_init`/`_fini` follow `memset` ahead of the read-only data. The vendor
block 0x08008924-0x08009044 is byte-exact apart from the two functions
named above; `RCC_GetClocksFreqValue` needed a register test at RCC+0x40
that no published SDK revision has.

### What had to be pinned first

The build was not reproducible against *itself*: Klipper stamps
`?-<timestamp>-<hostname>` into the dictionary it embeds, so two builds a
second apart differ. Nothing can be matched until that is fixed. Likewise
the deflate: Fedora's Python links zlib-ng, which produces different bytes
from classic zlib at the same level, for identical input.

The compiler configuration was then established by measurement, not
assumption -- each row is the count of instruction-identical handlers:

| | | |
|---|---|---|
| `-O2` | **32** | vs 10 (-Os), 3 (-O1), 28 (-O3), 3 (-Og) |
| `-mcpu=cortex-m4` | **32** | vs 8 for cortex-m3 |
| no LTO | **32** | vs 5 with Klipper's default `-flto -fwhole-program` |

Upstream Klipper builds with LTO; the stock image does not, which is
visible directly -- it *calls* `oid_lookup` where an LTO build inlines it.

### Three systematic FlashForge changes

Each one is a small edit repeated across the tree, and each unlocked many
functions at once.

1. **`shutdown()` latches an error code.** Every site writes a per-site
   constant to a global before shutting down, so the host can name the
   fault. All 30 sites recovered; the codes run sequentially in source
   order within each file, which is how the mapping was confirmed rather
   than guessed (gpiocmds.c lines 62/89/137/160/183 -> 29/30/31/32/33).
2. **`sched_add_timer()` takes a call-site tag.** On a "timer scheduled in
   the past" fault the tag is latched and reported as the `close` field of
   the board telemetry, naming which call site was late. All 13 sites
   recovered.
3. **The FlashForge commands live in `basecmd.c`,** between
   `clear_shutdown` and `identify`, and `ff_report_close()` sits at the end
   of the file. This is not a style choice: Klipper assigns message ids
   from the concatenated per-object `.ctr` files in `src-y` order, and in
   *reverse* declaration order within a file. Stock's ids put the six
   commands at 2-7, between identify (1) and clear_shutdown (8), which is
   only reachable from that one arrangement. Getting it right is what made
   the dictionary byte-identical.

   The file's *internal* order is now solved too. `.text` order is GCC's
   lexical definition order; `.ctr` order, which assigns the message ids, is
   *reverse* lexical order. Stock's emission order is inconsistent with its
   id order, which proves the `DECL` markers are not adjacent to their
   bodies in FlashForge's source. Decoupling them -- bodies in stock's
   `.text` order, `DECL_COMMAND`s in one block, six
   `DECL_CTR("_DECL_ENCODER ...")` markers restated after the bodies --
   reproduces stock exactly and collapses all fourteen handlers in the file
   onto one uniform offset. A restated `DECL_CTR` is one of several
   arrangements that would produce this; what is proven is that the two
   orders must be decoupled, and which way each must go. Also worth
   recording: the FlashForge block is definitively inside `basecmd.c`, not a
   separate object (ids 2-7 sit contiguously between `identify` at 1 and
   `clear_shutdown` at 8, and `.ctr` files are concatenated whole), and every
   function in the file already had stock's exact size -- only the order was
   wrong.

### What is still missing

No bytes. What is missing is the credibility of the source: the six dead
conditionals above stand where real code probably stood. That is the
open work on this board, and `PLAN.md` carries it.

### What the vector table turned out to be

Stock's table is 72 words: 16 system entries followed by 56 external
lines -- the N32G45x's real IRQ count -- with slots 53-55 zero because no
handler is declared for them. That resolves the array length: it is sized
for the silicon, not for the highest handler actually in use. Only four of
the external lines hold a real handler:

| slot | line | what |
|---|---|---|
| irq11 | DMA1_Channel1 | the eddy sensor's TIM1 latch |
| irq14 | DMA1_Channel4 | dead -- an abandoned DMA serial design |
| irq15 | DMA1_Channel5 | dead, likewise |
| irq36 | SPI2 | the USART1 handler -- see below |

Everything else is `DefaultHandler`, and all 72 words now agree with stock.
Honestly: a 69-word array plus alignment padding would produce identical
bytes now that the fill is known to be zero rather than `0xff`, so this is a
reading the binary cannot fully separate from the old one. But 56 external
lines is the one that explains the array length by the part's actual
interrupt count rather than by an unexplained tail.

## Two things worth knowing about

**The USART handler sits on vector 36, and that should not work.**
Stock puts a handler that services USART1 -- it reads the status register
at 0x40013800 and tests ORE/RXNE -- at vector slot 36, and unmasks NVIC
line 36 through `NVIC_Init`. On the published numbering that is the wrong
line: the N32G45x CMSIS header numbers this part exactly like an F103, a
contiguous enum in which 35 is SPI1, **36 is SPI2 and 37 is USART1**, with
the N32-only interrupts appended from 53 upward. Two independent SDK
mirrors agree, and there is no gap anywhere in 11..37 that could absorb an
off-by-one.

The obvious reading is a one-line bug in FlashForge's source. But it does
not survive contact with the rest of the image:

- the console is **not** DMA-driven. It is upstream Klipper's
  byte-at-a-time RXNE/TXE interrupt path, so it needs that interrupt;
- the DMA1 channel 4 and 5 handlers at 0x080083B4/0x080083F4 are real code
  but dead -- those channels are never configured or enabled and their
  NVIC lines are never unmasked (`NVIC_Init` has exactly three call sites:
  IRQ 11, IRQ 36 and SysTick);
- neither the SPI2 base address nor UART4's appears anywhere in the image;
- and the printer ships and works.

If the handler really were on SPI2's line, this board's console could not
receive a byte. So either the shipped silicon numbers USART1 at 36,
contradicting two published copies of the vendor header, or this image has
a defect that ought to be fatal. **The binary cannot settle it** -- that
needs the part's reference manual or a live board. An earlier revision of
this note asserted the bug as fact; that was premature.

Either way, reproducing the image requires the handler on slot 36, which
is what the tree now does.

### endstop_recover_state cannot reply


`endstop_recover_state` replies by calling `ctr_lookup_encoder()` directly
with a string literal instead of going through Klipper's `sendf()` macro.
That skips the `DECL_CTR` marker, so `endstop_recover_state oid=%c ok=%c`
is never registered as a response: the string sits in flash, the lookup
returns NULL at run time, and the reply goes to `command_sendf(NULL, ...)`.

It is not theoretical -- FlashForge's own klippy sends this command
(`klippy/mcu.py`, `MCU_endstop._recover_cmd`).  All three boards carrying
the command have it.  The patch reproduces the fault verbatim so that the
generated dictionary still matches; a fix is a one-line change to use
`sendf()`.
