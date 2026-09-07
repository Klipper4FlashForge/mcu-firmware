# Compiler shaping evidence, moved out of the tree

Recovering the levelBoard image meant writing statements in a particular
order, choosing the width and signedness of particular locals, and
occasionally spelling a branch out that a person would have folded. While
that work was in progress the reason for each such choice was written
inline, next to the statement it explained, in comments that talked about
GCC's passes, about register allocation, and about what the shipped image
does at a given flash address.

Those comments do not belong in a tree that is meant to read as the
firmware's own source, but the evidence in them is what makes the
recovery auditable, so it is kept here verbatim. Each heading names the
file and the function the comment sat in. The code itself is unchanged:
nothing here was acted on, only relocated.

See `recovery-log.md` for the narrative and `realism-audit.md` for the
standing list of everything in `klipper/` that still reads as
reconstruction.

---

## lib/n32g45x/ — the peripheral driver's function order

Stock's layout for this code, read off the image at 0x08008924-0x08009044
via relocmap.py/armdis.py, is misc -> gpio -> usart -> rcc -> tim -> dma,
in SDK definition order within each module.

The driver was first recovered as one file, `n32g45x_periph.c`, carrying
`__attribute__((no_reorder))` on all 33 functions to pin that order --
which no portable vendor SDK could use. It is now six files named for the
SDK's own modules (`misc.c`, `n32g45x_gpio.c`, `n32g45x_usart.c`,
`n32g45x_rcc.c`, `n32g45x_tim.c`, `n32g45x_dma.c`), listed in that order
on the link line, and no function carries `no_reorder`.
`-ffunction-sections` gives each function its own `.text.<fn>`, the
linker keeps input-file order, and within each of the six files GCC 10.3
emits in declaration order, so the link line alone reproduces stock's
layout -- at 0 differing bytes. Order between translation units was never
`no_reorder`'s business; only order within one was.

`noipa` on `TIM_InitTimeBase` and `TIM_InitTimBaseStruct` is a separate
matter and is still load-bearing: dropping it lets both inline into
`TIM_TimeBaseInit`, for 6,336 differing bytes and an image of 26,676.

## lib/n32g45x/n32g45x_gpio.c — GPIO_InitPeripheral

```
    // No early return for an empty pin mask: the loop guard handles it, and
    // an explicit return in front of it changes GCC's block layout.
```

## lib/n32g45x/n32g45x_tim.c — TIM_InitTimeBase

```
    // This is the stock driver's complete decision tree.  TIM6 uses the
    // reduced basic-timer path; the other instances configure the common
    // counter fields and the capture-input selectors supported by that
    // particular timer.  The basic-timer path is the else branch rather
    // than an early return: that is what places its code last, as in stock.
```

```
        // Stock's compiler saw the TIM8 test at even odds.  GCC 10 predicts
        // a pointer equality as 30 % taken, and that guess alone changes the
        // block layout; the weight below restores stock's layout.  The
        // spelling FlashForge used to get there is not known.
```

### TIM_TimeBaseInit and the one `noipa` that is left

`TIM_TimeBaseInit()` fills a file-static `TIM_TimeBaseInitType` by
calling `TIM_InitTimBaseStruct()` and then overwriting four of its
eleven fields. GCC's interprocedural analysis of the callee changes how
the caller schedules, so `TIM_InitTimBaseStruct` carries
`__attribute__((noipa))`. It is the analysis half that matters, not the
inlining: `noinline` alone and `noinline, noclone` both cost the same 6
bytes, and those 6 bytes are one `mov r1, r4` — the struct pointer for
the tail call — scheduled two instructions too early.

`TIM_InitTimeBase` had the same attribute and needs nothing at all, not
even `noinline`; it is gone. Measured and rejected for the remaining
one: all 24 orders of the wrapper's four assignments (best 4 bytes), and
dropping the wrapper's redundant `ClkDiv = 0` / `CntMode = 0` — which
`TIM_InitTimBaseStruct` has already done — at 6,203 bytes, so those two
redundant stores are stock's.

## lib/n32g45x/n32g45x_tim.c — TIM_ETRClockMode2Config

```
    // The prescaler is copied into a local before anything else so that
    // its SSA name is numbered before the register temporaries.  GCC
    // orders the operands of a commutative operation by SSA version, and
    // the two-operand Thumb orrs takes its destination from the first
    // operand: this is what puts the final orr into r1 (the prescaler's
    // register) at 0x08008E4C instead of r3.
```

```
    // Each arm stores the register itself; merging the arms into one
    // value lets GCC fold the set into an orr, where stock keeps the
    // shift-and-complement form.
```

## lib/n32g45x/n32g45x_dma.c — DMA_Init

```
    // Every configuration field is applied as its own read-clear-write
    // followed by a separate read-set-write of the channel config register,
    // which is what puts a paired bic/orr around each field in the image.
    //
    // Each field is read into an int local immediately before the pair that
    // applies it.  The locals being int matters -- the signed intermediate
    // keeps a conversion of its own in the tree, which fixes the order IRA
    // colours the fields in and holds the working set to {r4, r5}.
```

**Corrected.** The fields are *not* read a group ahead. They used to be
written that way, with `circ`, `prio` and `m2m` hoisted into a clump and
an `if (channel) X else X` at the `TXNUM` store making up the
difference; that combination reproduced the bytes but read as
scaffolding. Each declaration beside its own field, and no conditional,
reproduces them too. 96 placements of the three declarations were built:
three score zero, and one of the three is the uniform spelling.

The general point, which is worth more than the site: an identical-armed
conditional and a moved declaration do the same job. Both put a
register-defining insn at a chosen point in the RTL chain without
emitting an instruction. The declaration is source; the conditional is
not. **Before writing a placeholder, look for a declaration already in
the function that can move to where the placeholder would go.**

## lib/n32g45x/n32g45x_dma.c — DMA_GetIntStatus / DMA_GetFlagStatus

```
// DMA_GetIntStatus and DMA_GetFlagStatus are the same function twice, and
// GCC's identical-code folding is what makes stock's two copies differ:
// the second one comes out with the tst operands swapped.  Which copy a
// handler calls is therefore visible in the image: channel 5 uses the
// interrupt pair, channels 1 and 4 the flag pair.
```

## lib/n32g45x/include/n32g45x.h — TIM_TimeBaseInitType

```
    // The selectors are bool, not uint8_t: same size, but a bool load is
    // not a character access, so GCC may move it across the volatile
    // register stores in TIM_InitTimeBase, which is what stock's code does.
```

## src/basecmd.c — the DECL_CTR / DECL_COMMAND block

```
// Stock's .text order for this block is NOT the order the message ids
// demand.  The two are set by different machinery and are decoupled here:
//
//   .text order  = the order GCC emits the function bodies, which for this
//                  compiler and this TU is plain lexical definition order
//                  (-ffunction-sections, and the link keeps object order).
//   .ctr order   = the order the DECL_CTR markers land in
//                  .compile_time_request, which is *reverse* lexical order,
//                  and which is all buildcommands.py sees when it numbers
//                  commands (all DECL_COMMANDs first) and responses.
//
// So the bodies below sit in stock's .text order, and every marker whose
// id would otherwise move is restated afterwards in the order the stock
// dictionary requires.  A restated marker wins because it is later in the
// file, hence earlier in .ctr.
```

```
// Response ids.  Reversed, this is the order the stock dictionary numbers
// them in; the copies inside the bodies above land further down the .ctr
// and are ignored, because an id is handed out on first appearance.
// identify_response has a fixed id, so its position only decides when its
// parameter-type table is numbered: after the five FlashForge responses,
// which is where stock's command_parameters7 puts it.
```

## src/basecmd.c — command_remove_peel

```
    // The eddy front end updates both of these from the DMA interrupt, so
    // they are read as volatile: that is what keeps the peel read ahead of
    // the live-value read, which is the order stock's instructions have.
```

## src/basecmd.c — command_get_basic_param

```
    // The absolute value is written as a ternary because that is the form
    // stock's instructions show: GCC 10.3 at -O2 if-converts it to
    // cmp/it lt/neglt and schedules the subs after the ctr_lookup_encoder
    // call, where an if statement gets the branchless eor/sub idiom instead.
```

## src/endstop.c — command_endstop_home

Superseded. The flag used to be stored through a laundered pointer so
that the store would alias `e->ts` and stop the post-reload scheduler
sinking `e->ts = NULL` past it. Declaring `ff_eddy_pin_state` a
`volatile bool` does the same job by itself; the store is written by
name now. See "why `ff_eddy_pin_state` has to be a `bool`" below.

## src/endstop.c — command_endstop_query_state

```
    // Stock stores 1 to this flag on entry and 0 on exit; the exit store is
    // what makes the function 96 bytes rather than 88.
```

## src/stm32/gpio.c — regs_to_pin

```
// The port is found by walking digital_regs, as upstream does: the loop's
// exit probabilities give the port blocks, the bit loop and the merge
// point stock's order and stock's register assignment (0x08007fc0).
```

## src/stm32/stm32f1.c — gpio_peripheral

```
    // The stock port spells the two AF register paths separately.  It also
    // shifts the GPIO register value itself into the AF field; retain that
    // original quirk for binary and behavioral fidelity.
    // The branch probabilities decide where GCC parks the two out-of-line
    // blocks (the AFL write and the POTYPE write) relative to each other and
    // to the pullup tail; these weights reproduce stock's block order.
```

Retried and rejected since: writing the low half first, `if (pos < 8)`
with the two blocks swapped, costs 50 bytes, and selecting the AF
register through a pointer instead of branching costs 9,026. The
`__builtin_expect_with_probability` weights stand.

Three constants in this function were only constants, and naming them is
free. `(volatile uint32_t *)0x40021014` is `&RCC->AHBENR`; naming it
exposes a FlashForge bug, because the bit index beside it is computed
from `APB2PERIPH_BASE`, so an APB2 enable bit is being written into the
AHB enable register — bit 2 there is `SRAMEN`, and the GPIO clock this
line looks like it enables is enabled elsewhere. `(mode & 0xffffffef)`
is `mode & ~GPIO_MODE_OD`, and the test `- 1 < 2` on it is
"is it one of the two output modes". `r->DS = (2 << shift)` is
`GPIO_DC_8MA`.

## Makefile — CFLAGS

```
# -fno-shrink-wrap and -ffixed-r10 are not style choices: both were
# established by measuring instruction-identical functions against the stock
# image.  Stock places its prologues as if shrink-wrapping were off, and its
# compiled C never touches r10 -- where it needs a seventh callee-saved
# register it takes r11, and where it needs an eighth it spills to the stack.
# Reserving r10 reproduces that allocation everywhere (instruction-exact
# functions 212 -> 223 of 246 with no regressions); the earlier
# --param ira-max-loops-num=2 was compensating for the free register and
# costs two functions once r10 is fixed.
```

## src/generic/armcm_link.lds.S — .text

```
        /* Stock starts code at 0x08004120, twelve bytes past the end of its
           69-word vector table, and puts libgcc first: __udivmoddi4 sits at
           0x0800418C, ahead of the first command handler at 0x08004540. */
        /* Stock's text order falls straight out of "plain .text first,
           function-sections second".  Everything built without
           -ffunction-sections has a plain .text: crtbegin.o, all of
           libgcc.a, and the hand-written assembler in libc (memchr.S,
           setjmp.S, strcmp.S).  So 0x08004120..0x08004540 is
           __do_global_dtors_aux, frame_dummy, __aeabi_uldivmod,
           __udivmoddi4, __aeabi_ldiv0, memchr, setjmp, longjmp, strcmp --
           in link order crtbegin, -lgcc, -lc_nano -- and only then do the
           application objects begin, with command_config_analog_in at
           0x08004540.  libc's C files (__libc_init_array, memcmp, memcpy,
           memmove, memset) are function-sectioned and land at the end,
           which is where stock has them (0x08009044..0x0800910C). */
```

```
        /* __libc_init_array() (generic/armcm_startup.S calls it) ends with
           "bl _init", so crti.o/crtn.o's halves of _init and _fini are
           linked.  Stock has them right after memset, at 0x0800910C and
           0x08009118, ahead of the read-only data. */
        /* crtbegin.o's empty .eh_frame sits here in stock: the frame
           address that frame_dummy and __do_global_dtors_aux keep in their
           literal pools is 0x0800910C, the same address as _init. */
```

## src/sched.c — the dictionary ids and what can go through the macros

The two static strings and two encoders that `sched.c` reports are looked
up by name, with their `DECL_CTR` markers hoisted to file scope, because
the id a marker gets depends on its position in `.compile_time_request`.
Measured this round, so nobody retries it:

- `shutdown("sentinel timer called")` in place of the explicit
  `sched_shutdown(ctr_lookup_static_string(...))` costs 406 bytes, and
  costs the same 406 whether or not the hoisted marker is kept. A
  duplicate marker is not free: it adds a second entry and shifts every
  id after it.
- `try_shutdown("Timer too close")` in `sched_add_timer()`: 484 bytes.

What *is* free is everything that does not touch a marker.
`sched_report_shutdown()` now calls `ff_report_close()` instead of
repeating its body; with `noinline` dropped from `ff_report_close` GCC
inlines the call and emits exactly the same instructions, so the
duplicated source was never load-bearing — the `noinline` was what made
it look like it was.

## src/generic/armcm_link.lds.S — .bss

```
        /* Stock's variable order, read off the image from the literal
           pools of instruction-exact functions.  It is neither link order
           nor alphabetical: sched.c's shutdown_jmp sits between the eddy
           sensor's wake flag and its timer, and ff_shutdown_code between
           tmcuart's and trsync's wake flags.  -fdata-sections gives every
           variable its own .bss.<name> input section, so the order is
           imposed here rather than by moving definitions between files.
           crtbegin.o's plain .bss (completed.1, object.0) comes first,
           and the receive/transmit buffers onward are already in order. */
```

How much of the list is load-bearing was never measured until now, and
the guess in the audit ("about half are inert") was wrong. A greedy
one-at-a-time removal drops exactly one line, `*(.bss.tx_dma_active)`,
which is gone; every other line costs bytes on its own. The run of 25
consecutive `ff_eddy_*` lines is in declaration order and looks like it
should fall out of the wildcard, but removing that block as a unit costs
76 bytes and removing all 28 `ff_eddy_*` lines costs 128. The order is a
genuine interleave across object files, and no arrangement of source can
produce it.

## src/stm32/serial.c — the vector table tail

```
// Stock's vector table is 69 words long: IRQ 0..52.  IRQ 52 (UART4 on this
// part's numbering) is padded out to a DefaultHandler slot even though
// UART4's base address, 0x40004C00, appears nowhere in the image -- UART4
// is not used.  What actually causes the table to extend that far is not
// known (no peripheral in this range is otherwise touched); this
// declaration reproduces the table's length and bytes without asserting a
// mechanism for it.
```

## src/generic/armcm_timer.c — timer_reset

```
    // Tag unknown: 98 belongs to the FlashForge eddy timer (0x0800630c),
    // and no stock call site could be attributed to this one.
```

## src/generic/armcm_faults.c — the PendSV slot

```
// The PendSV slot points at DefaultHandler while the other unused system
// exception slots stay null (stock has 0x08008921 at offset 0x38).
```

## src/ff_flashforge.c — ff_pa_action

```
// The eBoard implementation (eBoard.hex 0x080115ec) reconfigures TIM4, TIM8
// and a DMA1 stream for the pressure-advance pickup.  Not reconstructed.
```

## scripts/buildcommands.py — Handle_arm_irq.generate_code

```
        # FlashForge leave the undeclared system-exception slots null and
        # only point the peripheral IRQ slots at DefaultHandler; stock
        # levelBoard has zeroes at 0x010..0x034 where upstream Klipper has
        # DefaultHandler.  armcm_offset is 16, so slots below it are the
        # system exceptions.
```

```
        # FlashForge size the array for the part rather than for the highest
        # declared handler: the N32G45x has 56 external interrupt lines, so
        # the array is 16 + 56 = 72 words and the slots past the last
        # initializer are zero.  Stock levelBoard has 0x00000000 at
        # 0x08004114..0x0800411F, where a 69-word array would leave linker
        # fill (0xff) instead.
```

## src/generic/armcm_startup.S — file header and DefaultHandler

```
// Stock builds this code from a vendor (ST-CubeIDE style) startup_*.s
// Reset_Handler: copy .data from flash, zero .bss, call SystemInit(),
// call __libc_init_array(), then hand off to main() (Klipper's
// armcm_main()).  This file reproduces that handler instruction for
// instruction so the reset vector and the code that follows it land at
// the addresses the vendor toolchain produced.
```

```
    /* stock pads the halfword to the next word with zero, not a nop */
```

## src/ff_eddy.c — `ff_eddy_median`

The ring copy is a plain loop, not `memcpy`: GCC turns it into the same
`ldm`/`stm` sequence, but a loop leaves the function pure in GCC's early
analysis, and the call heuristic does not mark a branch to a pure call
cold. That is what keeps `ff_eddy_update`'s smoothing path in line
rather than out of it.

The `noinline` on this function does nothing either, and is gone: the
purity argument above is about the loop, not the attribute.

The `__section(".text.eddy_median")` that used to sit on this function
placed nothing and has been deleted. `ff_eddy_median` is the first
function defined in `ff_eddy.c`, so `-ffunction-sections` and the
script's plain `*(.text.*)` already put it where stock has it. It was
left over from a stage when the `.text` block was written differently.

## src/ff_eddy.c — `ff_eddy_home_reset`

Six plain C stores, and the two things that make them come out as
stock's seventeen instructions are `ff_eddy_hard_trigger`'s type (`bool`,
not `uint8_t`) and the non-volatile reference the `ff_eddy_trig_count`
store goes through. The long form is at the end of this file.

## src/ff_eddy.c — `ff_eddy_isqrt`

The zero guard's `unlikely()` probability is inlined into
`ff_eddy_update`, where it sets the count of the shared join block after
the iteration. At the default 34 % that block outranks the saturating
3\*MAD arm in bb-reorder's trace order; stock places the 3\*MAD arm
first, which needs the guard cold.

## src/ff_eddy.c — `ff_eddy_counter_init`

The `GPIO_InitType` lives in its own scope: with an addressable local in
the outer scope GCC will not turn the trailing `ff_eddy_dma_init()` into
a tail call.

The TIM1 pointer used to be spelled `(TIM_Module *)((char *)NS_TIM8 -
0x800)`, transcribed from the instruction that computes it. `NS_TIM1` is
the same address and the same bytes. Nothing in this function needed the
subtraction; the two `RCC_EnableAPB2PeriphClk` arguments, the DMA init
struct's eight literals, the channel remap, the TIM DMA request and the
three GPIO fields were bare hex for the same reason, and are all named
now.

## src/ff_eddy.c — `ff_eddy_update`

The two comparisons in the armed path are written threshold-first
because that is stock's order, and `adev` is a PHI of two `uint16`
conversions, so phiopt does not fold it into `ABS_EXPR` and combine
reuses the subtraction's flags for the sign test. The baseline load and
the counter increment sit before the compare so tree-ssa-sink keeps them
in that block. The `unlikely()` on the ring wrap makes the fall-through
edge hot enough that the `ring_pos` store stays put. The early return on
`!have_filter` gives the smoothing path the predictor's 66 % and puts
`&filter_acc`, not `&have_filter`, in r9. The insertion sort's inner
compare reads through a named `cur` so the key is the first operand by
SSA version order. The sigma floor is computed as a signed temporary and
then converted, which gives the floor its own SSA name, separate from
the add. The absence of a `return` after the quiet-timer store matters:
an explicit return that is not the function's last statement carries the
gimplifier's early-return prediction of 66 %. `mad != 0` is tested first
so bb-reorder's `prev_bb` tie-break places the `mad_limit` block after
the saturating arm. `calibrated` is stored right after `have_filter`
because sched2 emits those independent plain stores in source order.

The `ff_eddy_mad` placeholder buys one free reference to
`&ff_eddy_ring_pos`. Without it the pointer lands in r7 instead of
stock's r6 and 21 bytes differ across the whole function — same
instructions, same order, same size, one register apart. `volatile` on
`ff_eddy_mad` is load-bearing here too: dropping it costs the same 21
even though the variable is write-only and a plain global would keep the
store alive, which is the opposite of what happened with
`analog_in_value`.

## src/ff_eddy.c — `ff_eddy_rebaseline`

`ff_eddy_hard_trigger` and `ff_eddy_trig_count` are volatile so that the
stores after `irq_enable()` keep program order; that is the only
spelling that reproduces stock's store order and register colouring
here. `ff_eddy_check_trigger` and `ff_eddy_update` compile the same with
or without it. The trailing store order — `calibrated` last, so its
address takes r3 — is what GCC's sched1 pressure model plus IRA need.

## src/ff_eddy.c — `ff_eddy_check_trigger`: what the four placeholders buy

Measured by deleting each one and rebuilding:

| site | delete it → | what changes |
|---|---|---|
| A `if (value < FF_EDDY_VALUE_MIN)` | 14 bytes differ | `subs r4,#1` sinks before `bl irq_enable`, so `value-1` rather than `value` lives across the call; `value`/`state` swap r4/r5 |
| B `if ((uint32_t)thr > value)` | 7 bytes | `thr` and `baseline` swap r7/r4 |
| C `if (value - 1 >= 0xfffe)` | 3 bytes | only the hard arm's range check: `subs r3,r5,#1 / movw r2` reverses to `subs r2 / movw r3` |
| D `if (value < baseline)` | 10,366 bytes, size 0x108 → 0x10C | `baseline` dies at `subs r5,r4`, IRA recycles r4 for `diff`, so the abs needs `ite lt / uxthlt / uxthge` instead of `neglt / uxth` |

Each site needs exactly one free reference, and the currency is
specific: A needs a use of `value`, C a use of `value - 1`, B a use of
`thr` alone, D a use of `baseline` alone. `value == 0xffff` fails at A
because fold rewrites it to `_1 == 65534`, which is C's currency.

`DMA_Init` shows what to look for next here (see its section above): a
*declaration* moved to the placeholder's position buys the same free
reference and is real source. `ff_eddy_check_trigger` has no spare
declaration to move — `value`, `hard`, `state`, `baseline` and `thr` are
all read under `irq_disable()` and cannot move out of it — but that is
the shape of the fix if one exists. The `ff_eddy_update` placeholder was
swept that way and has none either: 96 placements of `devs`, `i`,
`si, sj` and a split `mad` declaration all score the same 21 bytes.

Also swept and rejected at A and C: both orders of the two counter
resets, braced and unbraced `if (state)`, dropping the `if (state)`
guard entirely (2,790 bytes — stock has the guard), and three spellings
of `ff_eddy_value_bad` (`== 0 || > 0xffff`, `- 1 > 0xfffe`, a `uint16_t`
round trip; the third costs 2,867).

## src/ff_eddy.c — the telemetry hypothesis is dead

`PLAN.md` proposed that real telemetry or debug statements supplied
these references as a side effect, and named `ff_eddy_last_dev`,
`ff_eddy_dbg_baseline` and `ff_eddy_offset` as the residue. Three
measurements close it:

- **The byte map is complete.** All 111 stock instructions in
  `0x08007C98..0x08007D76` map to statements already in the source.
  There is no unexplained `str`, so no real telemetry statement can live
  in this function.
- **`ff_eddy_last_dev` is not write-only.** Its address `0x20000134`
  appears exactly once in the image's literal pools, at `0x08007D94`.
  Stock stores it at `0x08007CEC` *and reloads it at `0x08007CEE`* —
  which proves it is volatile and that the filter reads it back. It is a
  live intermediate, already modelled. `ff_eddy_dbg_baseline` is touched
  only in `ff_eddy_timer_event`, and `ff_eddy_offset` only in
  `ff_eddy_rebaseline` and the recalibration tail. Neither is referenced
  from `ff_eddy_check_trigger` at all.
- **A write-only store cannot pay for a reference.** Adding
  `static uint32_t ff_eddy_dbg_hard; … ff_eddy_dbg_hard = value;` in
  place of site A reproduces the deletion diff exactly (14 bytes), and
  in place of D likewise (10,366). GCC 10 removes stores to write-only
  statics together with the reference.

So "stock's hard arm holds something not reconstructed" resolves to
something smaller than it looked: stock's hard arm references
`value - 1` a second time and `value` once more inside `if (state)`. It
holds no extra instructions.

## src/ff_eddy.c — ruled out at these sites, do not retry

- The ternary form `x = c ? v : v` at any site (A 14, B 7, D 10,366):
  the front end folds it, so it must be a statement-level `if`/`else`.
- An empty body `if (c) { }` (3 bytes).
- Merging A's and C's conditions into one `if` at either site (9 or 3).
- Moving D to the `else` arm, the untrig tail, or the trig tail
  (10,366 / 10,366 / 13).
- `value - 1 == 0xfffe` or `value >= 0xffff` at C: fold rewrites both to
  `value == 0xffff`, the wrong currency.

## src/ff_eddy.c — what the range-check round fixed

The guards at both range checks were `value - 1 > 0xfffe`, which is not
how a person writes that constant — `movw` is forced only because
0xFFFE is not a Thumb-2 modified immediate, and says nothing about the
source. `ff_eddy_value_bad()`, a `static int` returning
`value == 0 || value > 0xffff`, is inlined to the same `_1 > 65534` and
builds at 0 differing bytes. Site C must still be spelled with the
literal `value - 1`, since that is what shares the SSA name with the
hard guard's subtraction.

## src/endstop.c — why `ff_eddy_pin_state` has to be a `bool`

`command_endstop_home`'s disarm path ends in four stores, and stock emits
`e->ts = NULL` before the pin store. Written as plain C with a `uint8_t`
flag, GCC emits them the other way round, for four differing bytes.

The decision is sched2's, and it is a priority decision rather than a
tie. Each of the four stores has one forward dependence, on the epilogue
`pop`. The three `uint8_t` stores are in alias set 0 — character types
alias everything — so they take a memory dependence on the epilogue's
frame reloads, `dep_cost` 1, priority 6. The pointer store has a non-zero
alias set, no such dependence, `dep_cost` 0, priority 5. The lowest
priority is scheduled last, so `e->ts = NULL` sank past the pin store.

Declaring the flag `volatile bool` gives its store a non-character alias
set too. Both drop to priority 5, the priority heuristic no longer
separates them, and the tie-break falls through to LUID: `e->ts` before
the pin, which is stock's order. The flag is a two-valued endstop level,
so this is the type it should have had from the start.

Address-taking is not the lever — an `always_inline` helper taking
`&ff_eddy_pin_state` still costs the four bytes. It is alias *sets*, not
points-to information.

## Two mechanism facts, established by measurement

Both were assumed wrongly in earlier comments in the tree, and both close
off or open up whole classes of hypothesis. Keep them in mind before
concluding that any ordering "cannot be produced by real source".

**`.text` order is not lexical definition order.** GCC 10's
`expand_all_functions()` emits in `ipa_reverse_postorder` of the
callgraph, and only then by declaration order — so callgraph edges
reorder emission. There is a counterexample in this tree: `sched.c`
defines `periodic_event`, `ff_eddy_timer_event` and `deleted_event` in
that order, and `sched.o` emits `.text.deleted_event` first.
`basecmd.o` comes out in definition order only because its handlers are
callgraph leaves.

**`.bss`/`.data` order is fully determined by two rules, and the shipped
image uses both.** With `-fdata-sections`, GCC emits `.bss.<name>` /
`.data.<name>` **sorted alphabetically**, regardless of declaration
order — `serial_irq.c` declares `transmit_buf, transmit_pos,
transmit_max` and emits `transmit_buf, transmit_max, transmit_pos`.
Without `-fdata-sections`, a file contributes one `.bss` in **reverse
declaration order**. `ld` for an unsorted `*(.bss.*)` walks input files
in link order and, within a file, section-header order. So the natural
result is link order x alphabetical.

That is enough to explain most of what the linker script was pinning by
hand. `basecmd`'s thirteen-variable run is alphabetical rather than in
`basecmd.c`'s declaration order, which is positive evidence that the
shipped build used `-fdata-sections`. The 25-variable `ff_eddy` run is
not alphabetical but is exactly that file's forward declaration order,
which is what a `-fno-data-sections` compile gives — so FlashForge's eddy
translation unit was probably not built with the shared flags.

The one part that no link order, file split or flag choice can produce
is the eleven-variable interleave: `shutdown_jmp` and `task_start` are
statics of `sched.c`, `tmcuart_wake` of `tmcuart.c`, `trsync_wake` of
`trsync.c`, and they occupy non-adjacent slots. A single object cannot
appear twice on a link line. That list is ours.

## src/ff_eddy.c — `ff_eddy_home_reset`: how plain C reaches it

Solved.  The body is six assignments in their natural order:

```c
ff_eddy_trig_acc = 0;
*(uint8_t *)&ff_eddy_trig_count = 0;
ff_eddy_untrig_count = 0;
ff_eddy_pin_state = true;
ff_eddy_hard_trigger = false;
ff_eddy_peel = 0;
```

with `ff_eddy_hard_trigger` declared `static volatile bool` rather than
`static volatile uint8_t`.  Seventeen instructions, stock's register
colouring, stock's literal-pool order, whole image at 0 differing bytes.

Two constraints have to hold at once, and each rules out the obvious way
of satisfying the other:

* **`ff_eddy_pin_state = true` must be the fourth statement.**  In sched1
  the GENERAL_REGS budget is 6 and LR takes one, so a fifth hoisted
  address load pushes pressure to 7 and the allocator takes r5 as well as
  r4.  Hoisting stops at four only when a register-defining insn sits
  between the fourth and fifth address load in the original chain, and in
  a body of constant stores the only candidate is the materialisation of
  the `1`.  Hence `pin_state` fourth — and hence the three statements
  before it must be stores GCC is free to sink below it, which means not
  volatile.  `ff_eddy_trig_acc` and `ff_eddy_untrig_count` are already
  plain; `ff_eddy_trig_count` is not, which is why its store here goes
  through a non-volatile lvalue.  Declaring the variable itself plain also
  satisfies this function but costs 10,371 bytes in
  `ff_eddy_check_trigger` and `ff_eddy_rebaseline`; the cast is local and
  free.  Exactly three other sites need that volatility — the store in
  `ff_eddy_rebaseline` and the *else* arms of two of the
  `ff_eddy_check_trigger` placeholders — which is itself a hint about
  what those placeholders stand in for.
* **`ff_eddy_peel = 0` must be emitted last, after `ldr.w r4,[sp],#4`.**
  That needs its store to sink past `ff_eddy_hard_trigger`'s, and with
  `hard_trigger` a `uint8_t` it cannot: sched2's RTL alias oracle prices a
  character-typed MEM in alias set 0, which conflicts with everything, so
  the two stores stay in program order.  As a `bool`, `hard_trigger` gets
  its own alias set, `peel`'s store sinks, `hard_trigger` takes r4 and
  `peel` takes r2 — which is what puts one store after the epilogue reload
  and gives the literal pool its `…, peel, hard_trigger` tail.

Why the earlier verdict said this was impossible.  Every sweep had held
the *declared types* fixed: 720 orders x 64 volatility masks, and
720 x 15 declaration subsets, all vary who is `volatile`, never who is a
character type, so the second constraint above was unreachable in the
whole search space.  Re-running that same grid across the two flag types
(`pin_state`, `hard_trigger` in {`bool`, `uint8_t`}) — 184,320 builds —
puts three configurations at 0, all of them the natural statement order
with `hard_trigger` a `bool`.

Scoring hid it a second time.  The winning configuration needs
`trig_count` plain, which regresses `ff_eddy_check_trigger` by 4 bytes and
shifts every function after it, so the *whole-image* score of the exact
answer is 10,371 — indistinguishable from noise.  Score the one function
against its own instruction stream, then pay for the rest separately.

The general lesson, which applies to every remaining open function: an
exhaustive search is only exhaustive over the axes it varies, and a
whole-image byte count is the wrong metric for a candidate that fixes one
function and breaks another.


## src/ff_eddy.c — `ff_eddy_check_trigger`: the debounce counters

Asked and settled from the bytes: the arms really are
`ff_eddy_untrig_count = 0; if (++ff_eddy_trig_count < 4)`, not
`= 1` with a plain compare. Stock's `0x08007D0C`/`0x08007D0E` are
`adds r3,#1 / uxtb r3,r3`, the `cmp` at `0x08007D12` tests that
incremented value, and `0x08007D16` stores it back; the constant put in
the opposing counter at `0x08007D10` is `movs r1,#0`. The mirrored arm at
`0x08007D44`-`0x08007D4E` is the same. All four reset sites in the
function store zero. The `= 1` reading would also pin the counter at 1
for ever, so it is not just a different spelling.
