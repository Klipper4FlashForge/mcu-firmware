# The levelBoard tree: what still reads as reconstruction

The image is byte-identical and that is now a gate, not a goal. This file
is the standing list of everything in `klipper/` that betrays how it was
made — constructs no FlashForge engineer would have written, and comments
written by an archaeologist rather than an author.

The rule for every entry: **a fix that changes one byte is not a fix.**
`cmp -l out/klipper.bin stock/levelBoard.bin | wc -l` must stay at 0.

Five classes, worst first. What has been closed so far is logged at the
end.

---

## A. Load-bearing constructs that are not source

Code that exists only to move GCC 10's register allocator or its
post-reload scheduler onto stock's choice. These are the ones that make
the tree indefensible as "FlashForge's source".

| # | site | construct | status |
|---|---|---|---|
| A1 | `src/endstop.c` `command_endstop_home` | `__asm__("" : "=r"(free_run) : "0"(&ff_eddy_pin_state))` — launders the flag's address so the store aliases `e->ts` | **fixed** — `ff_eddy_pin_state` is a `volatile bool`, 0 bytes |
| A2 | `src/generic/serial_irq.c` `serial_get_tx_byte` | `asm volatile("" : : "r"(npos) : "memory")` — orders the `transmit_pos` store ahead of the `writeb` | open, costs 4 bytes without it |
| A3 | `src/ff_eddy.c` `ff_eddy_check_trigger` | four conditionals whose two arms are textually identical | open, see `PLAN.md` |
| A4 | `src/ff_eddy.c` `ff_eddy_update` | one identical-armed conditional on `ff_eddy_ring_pos` | open |
| A5 | `lib/n32g45x/n32g45x_dma.c` `DMA_Init` | one identical-armed conditional | open |
| A6 | `src/ff_eddy.c` ×2 | `value - 1 > 0xfffe` as a zero/overflow reject — not how a person writes that constant | **fixed** — `ff_eddy_value_bad()`, 0 bytes |
| A7 | `src/stm32/gpio.c` | `extern volatile uint8_t ff_eddy_pin_state_v __asm__("ff_eddy_pin_state")` — an asm-label alias to get a second, volatile view of a variable already declared in a header | **fixed** — unnecessary once the flag is a `bool`, 0 bytes |
| A9 | `src/ff_eddy.c` `ff_eddy_home_reset` | the entire function was a `naked` body of hand-written Thumb assembly standing in for six C assignments | **fixed** — six plain C assignments, 0 bytes; one `*(uint8_t *)&` cast remains |
| A10 | `src/ff_eddy.c` | `__section(".text.eddy_median")` on `ff_eddy_median`, a magic section name that exists to place the function | open |
| A11 | `src/stm32/stm32f1.c` ×2, `lib/n32g45x/n32g45x_tim.c` ×1 | `__builtin_expect_with_probability(cond, 1, 0.6)` — a GCC-specific builtin, with a hand-tuned probability, used to steer block layout. No firmware author reaches for this | open |
| A8 | `src/stm32/stm32f1.c` `armcm_main` | was `asm volatile("movs r3, #0\n msr primask, r3")`, an undeclared-clobber hand assembly of a CMSIS intrinsic | **fixed** — `__set_PRIMASK(0)`, 0 bytes |

A3/A4's placeholders survive, but they now carry honest "NOT
FLASHFORGE'S SOURCE" markers rather than compiler essays, and three of
the four read as sanity checks (`value < FF_EDDY_VALUE_MIN`,
`(uint32_t)thr > value`, `value < baseline`) instead of arbitrary
equalities — all at 0 bytes. The telemetry hypothesis that `PLAN.md`
led with is now falsified; see `notes/compiler-shaping.md`.

A9 is closed, and the earlier "ruled out" verdict here was wrong. Two
levers had never been varied together: the *type* of
`ff_eddy_hard_trigger` and the *volatility of the one store* in this
function. With `ff_eddy_hard_trigger` a `bool` rather than a `uint8_t`,
and `ff_eddy_trig_count` cleared through a non-volatile reference, the
six assignments in their natural order compile to stock's seventeen
instructions and its literal-pool order exactly. The function is now
plain C; the residue is one cast, and it is marked in the source. See
`compiler-shaping.md` for the mechanism and for what the exhaustive
search had actually covered.

Ruled out for A11: the builtins are load-bearing. Plain `if (pos & 8)`
costs 47 bytes, `likely()` 42, a plain `pullup < 1` 42, and a plain
`TIMx == NS_TIM1 || TIMx == NS_TIM8` 6,585. What is free is reshaping
the code around them: the pull-up tail now reads
`if (pullup > 0) … else if (pullup) …` instead of a `pullup < 1` test
with an unreachable inner branch, at 0 bytes.

Measured and ruled out for A1: all 24 orderings of the four stores (best
4 bytes), and `struct trsync * volatile ts` (10 bytes, worse).
A2 is now the only empty `asm` left, and it survives. sched2 has both
candidates at priority 1 and breaks the tie with its last-scheduled-insn
heuristic, which promotes the consumer of `adds r0,r2,#1`. Only a memory
dependence between the buffer load and the `transmit_pos` store would
reverse it, and the two are distinct declarations, so no legal C spelling
creates one. Both operands of the barrier are load-bearing: `"memory"`
supplies the dependence, and `"r"(npos)` pins the `adds` above it —
without that the add sinks, r4 is freed and the function shrinks by eight
bytes. Ruled out, do not retry: `barrier()` (830), upstream's
`*pdata = transmit_buf[transmit_pos++]` (830), `writeb`/`readb` in every
position tried (855, 8383, 21, 38), `transmit_pos`/`transmit_max`
volatile (8000+), and retyping or reordering the locals (4 each).

## B. Reproduction scaffolding wearing vendor clothes

These are ours, they are necessary, and pretending otherwise is the
problem. The fix is not to delete them but to stop dressing them as
FlashForge code — name them for what they are and keep them together.

- `Makefile`: `ff-link-y` / `ff-link-tail-y`, a second link-order list
  parallel to `src-y`.
- `scripts/buildcommands.py`: the `KLIPPER_BUILD_VERSION` override and
  the `compress_dict()` ctypes shim onto a classic `libz`.
- `src/generic/armcm_link.lds.S`: fifty hand-listed `*(.bss.<name>)`
  lines imposing stock's variable order. About half of them are inert —
  they restate link order x alphabetical, which is what the plain
  wildcard already gives. See `compiler-shaping.md` for which parts are
  derivable and which are not. The `.data` block is **fixed**: it is
  upstream's `*(.data .data.*)` again. The invented `.data.ff000` /
  `.data.ff10x` section names are **fixed**: the linker script now names
  the four variables the way it already named the `.bss` ones, the
  `__attribute__((section(...)))` stamps are gone from the C source, and
  `ff_eddy_mad_limit` is a plain global rather than a `static` that GCC
  folds out of `.data`. 0 bytes.
- `src/basecmd.c`: the block of `DECL_CTR` / `DECL_COMMAND` markers
  restated at the end of the file to force stock's message ids, when the
  bodies above already sit in stock's `.text` order.
- `src/sched.c`, `src/stm32/hard_pwm.c`: `DECL_CTR("_DECL_STATIC_STR …")`
  lines that re-register strings whose code was deleted, purely to keep
  the dictionary.

## C. Surgery on upstream that no one would perform

Upstream code deleted until the bytes agreed, leaving stubs that read as
damage rather than as decisions.

- `src/stm32/n32g45x_adc.c`: the whole driver gutted. `gpio_adc_read()`
  returns 0, `gpio_adc_setup()` returns `.adc = 0` after an orphaned
  `udelay(10)`, the calibration and channel setup are gone. Stock really
  does stub these — the question is only whether FlashForge's own source
  stubbed them this way or configured the ADC out.
- `src/stm32/hard_pwm.c`: `gpio_pwm_setup()` reduced to
  `return (struct gpio_pwm) { };` with ninety lines removed, while three
  `DECL_CTR` lines keep its deleted error strings alive.
- `src/initial_pins.c`: the `if (sizeof(CONFIG_INITIAL_PINS) <= 1) return;`
  guard simply deleted.
- `src/Makefile`: `spicmds.c` and `i2ccmds.c` dropped from `src-y`
  outright rather than configured off.
- `src/generic/armcm_boot.c`: a hundred lines of boot code removed. This
  one is defensible — the startup really did move to `armcm_startup.S`.

## D. Fictions and unattributed magic

- `src/ff_flashforge.c`: `ff_pa_action()` is an empty body under a comment
  citing `eBoard.hex 0x080115ec` and admitting it was not reconstructed.
- `src/generic/armcm_timer.c`: `sched_add_timer(&wrap_timer, 0)` under
  "Tag unknown: … no stock call site could be attributed to this one."
- `sched_add_timer()`'s new `tag` argument is passed as bare numbers at
  fourteen call sites — 0, 1, 14, 15, 22, 23, 31, 45, 48, 56, 98 — with
  no enumeration and no names.
- `src/basecmd.c`: `FF_MCU_YEAR` / `FF_MCU_DATE` / `FF_MCU_VERSION` under
  "levelBoard.hex reports these three constants verbatim".

## E. The voice

Roughly two hundred comment lines across twenty-one files are written
from outside the code looking in: they cite flash addresses, name GCC's
passes, and say what "stock" does. Worst offenders by line count:
`src/ff_eddy.c` (107), `lib/n32g45x/n32g45x_tim.c` and `n32g45x_dma.c` (17),
`src/generic/armcm_link.lds.S` (14), `src/basecmd.c` (12).

The evidence itself is worth keeping — it is what makes the recovery
auditable — but it belongs in `notes/`, beside the disassembly it was
read from, not in a file that claims to be firmware source. Most of the
hardware archaeology in `ff_eddy.c`'s header is already in
`notes/eddy-sensor.md` verbatim.

---

## Closed

Every item below rebuilt at 0 differing bytes and was folded into the
tree. None of it cost a single byte.

**Constructs replaced by what an author would write**

- `armcm_main`: hand-written `movs r3,#0 / msr primask,r3` with an
  undeclared r3 clobber → `__set_PRIMASK(0)`. Stock has both this and
  `cpsie i`, so the redundancy is FlashForge's; only the spelling was ours.
- `ff_eddy.c`: `value - 1 > 0xfffe` at both guards → a named
  `ff_eddy_value_bad()` helper. The `movw #0xfffe` was only GCC's
  lowering of a range test and never implied the source wrote `- 1`.
- `ff_eddy.c`: five thresholds spelled `> N - 1` / `<= N - 1` → `>= N`
  and `< N`. The uniformity across all five was the tell: constants
  transcribed from immediates rather than written from the spec.
- `ff_eddy.c`: `if (floor_sd < 1)` on a `uint32_t` → `if (!floor_sd)`.
- `ff_eddy.c`: `DMA1_Channel1_IRQn`, which resolves to ST's F103 enum,
  → this part's own `N32_DMA1_Channel1_IRQn` (the same integer, and the
  N32 macro had been defined and never used).
- `gpio_peripheral`: `pullup < 1` guarding an inner `if (pullup)` — an
  unreachable branch — → `if (pullup > 0) … else if (pullup) …`.
- `gpio_peripheral`: `((uint32_t)r + 0xbfff0000) >> 10`, a subtraction
  written as its two's complement, → `((uint32_t)r - APB2PERIPH_BASE)`.
- `NVIC_PriorityGroupConfig(0x700)` → `NVIC_PriorityGroup_0`, which the
  header already defined and nothing used.
- `SystemInit()`: the N32 clock tree was `rcc[11] = 0x3800` — registers
  addressed by array index off a hard-coded base, with twenty unnamed
  masks. Now an `RCC_Module` struct and a `FLASH_Module` in the vendor
  header, with named bit constants throughout, and `SCB->VTOR =
  FLASH_BASE` in place of a literal.
- `digital_regs[]` was declared `GPIO_TypeDef *` and cast to
  `GPIO_Module *` at all eight uses. It is now declared as what it is.
- 30 `shutdown_ec()` call sites carried bare integers with tell-tale
  gaps (no 3-10, no 13, no 17-21, no 28) → a named enumeration in
  `ff_flashforge.h`. The gaps now read as retired codes.
- `lib/n32g45x/n32g45x_periph.c` carried `__attribute__((no_reorder))` on
  all 33 of its functions -- a GCC-only attribute that pins emission order
  within one translation unit, which no SDK that must also build under
  ARMCC and IAR could use, and which uniformly on every function read as a
  script pass. Split into the six files the real SDK names -- `misc.c`,
  `n32g45x_gpio.c`, `n32g45x_usart.c`, `n32g45x_rcc.c`, `n32g45x_tim.c`,
  `n32g45x_dma.c`, with the private core and RCC definitions in
  `n32g45x_internal.h` -- and listed in that order on the link line. Order
  *between* objects is the link line's job, which is how this tree already
  places everything else; within each of the six, GCC emits in declaration
  order on its own. All 33 attributes are gone and no function needed
  reordering. Removing the 33 from the single file had cost 477 bytes, and
  a greedy one-at-a-time removal could drop only 1 of 31.

- `.data.ff000` / `.data.ff10x`: invented section names stamped into the
  C source → the linker script names the four variables, as it already
  did for `.bss`. `ff_eddy_mad_limit` became a plain global, which is
  what had needed the attribute.

**Things that should not have been in the tree at all**

- `hard_pwm.c`: 260 lines of `pwm_regs[]` and `struct gpio_pwm_info`,
  unreferenced since the two functions above them were stubbed, and
  never emitted. Deleted.
- `stm32f1.c`: `clock_setup()` and `stm32f1_alternative_remap()`, both
  callerless (GCC warned), plus `STM_OSPEED` and a dead
  `armcm_reset.h` include. Deleted.
- `stm32f1.c`: an `extern` for `NVIC_PriorityGroupConfig` three lines
  after the header that declares it, and a `../../lib/...` include path
  where every other file uses the include directory. Both fixed.
- `serial.c`: the generic F1 `#else` branch — which this build never
  compiles — had been left reserving `PH10,PH9` while the macros three
  lines below said PA10/PA9, and putting the console on `SPI2_IRQn`.
  Reverted to upstream.
- `ff_eddy.c` and `ff_flashforge.c`: includes annotated for `NULL`,
  `memcpy`, `VectorTable`, `gpio_out_setup`, `DECL_COMMAND`, `DECL_TASK`,
  `irq_disable` and `sendf`, none of which those files use. Four were
  dead outright.
- `ff_flashforge.h` declared half the interface, so `sched.c` carried
  three `extern`s for its own module's entry points, one of them inside
  a function body. The header now declares them all.
- `adccmds.c`: `static volatile uint16_t analog_in_value`, file-local
  and never read, where `volatile` was the only thing keeping the store
  alive. Now a plain global with external linkage, declared in the
  shared header.
- `armcm_startup.S` and `armcm_faults.c`, both wholly new files, carried
  Kevin O'Connor's 2019 copyright. Corrected.

**Question closed**

The audit's class C asked, of each gutted driver, whether stock really
stubbed it or whether we deleted live code. Disassembly of the
byte-identical image answers it for every site checked: `gpio_adc_read`
really is `movs r0,#0 / bx lr`, `gpio_pwm_setup` really is
`movs r0,#0 / bx lr`, `initial_pins_setup` really has no size guard, and
`irq_wait` really uses `nop` rather than `wfi`. Nothing in that slice was
live upstream code removed to make bytes agree — the tree's problem is
how the source is spelled, not what it does.

**Also closed** (all 0 bytes)

- The `.data` placement block — a `KEEP`, an `EXCLUDE_FILE` and a
  per-object line — is gone; the section is upstream's
  `*(.data .data.*)` again. Moving `ff_trigger_threshold` into
  `basecmd.c`, the file that owns its command and its only writer, was
  the whole of it: it is the first object in link order with any
  `.data`, so it lands at `0x20000000` on its own.
- `. = ALIGN(16)` before `.text` was a no-op — the 72-word vector table
  already ends 16-aligned. Deleted, with its comment.
- `ff-link-y`, fifteen hand-written filenames, is now
  `$(sort $(foreach ...))` over `src-y` — it was always exactly the
  alphabetical sort of the upstream core objects. (`%/%` is not a valid
  make pattern: only the first `%` is a wildcard.)
- `src/Kconfig` had upstream's `depends on HAVE_LIMITED_CODE_SIZE`
  deleted so the board could turn optional features off. Restored, with
  `select HAVE_LIMITED_CODE_SIZE if MACH_N32G45x` in `src/stm32/Kconfig`
  beside the two existing ones — the upstream idiom verbatim.
- `ff_eddy_pin.c` was linked but absent from `src-y`, so any `DECL_CTR`
  added to it would have been silently dropped from the dictionary. Now
  declared.
- `-ggdb3` dropped from the release CFLAGS.

**Measured, does not hold:** moving `ff_endstop_active` from
`ff_flashforge.c` to `endstop.c` (its only user, and `endstop.o`'s slot
is where stock places it) costs 6 bytes. The linker-script line stays.
