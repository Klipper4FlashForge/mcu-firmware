# mainBoardGD recovery plan

Session record: 2026-09-11. MainBoardGD is the selected board. Stock
extraction, C reconstruction and isolated byte matching are in progress.
The whole image now has a score (`tools/build-gd-image.py`). The canonical
build is Arm Compiler 6.20 at µVision's default `-O1`
([compiler-version-sweep](notes/compiler-version-sweep.md)): **224/281
functions exact, 35,009/45,552 image bytes** (ATfE 22.1.0, the previous
canonical compiler, gave 187 and 30,743). The vendor SDK spans are no longer
hand reconstructions: GigaDevice's own GD32H7xx library V1.1.0 is compiled
from `recovered/lib/gd32h7xx` (`tools/check-gd-sdk.py`), which made
`timer_init`, `timer_input_trigger_source_select`, `nvic_irq_enable`,
`mpu_region_config` and a dozen more exact at once. Still open there:
`rcu_clock_freq_get`, the DMA flag/init bodies, `adc_special_function_config`
and `adc_interrupt_flag_get` differ from V1.1.0 as compiled - a different
library version or FlashForge edits; the hand ADC special body that matched
(92/92) is worth reconstructing from stock again.

| Area | Established | Still open |
|---|---|---|
| Generated layer | typed C data exact over 4,536 bytes; encoder lookup exact over 640 bytes including pool; three generated runners exact over 114 bytes; retained `.ctr` exact and integrated | static lookup has 70 differing bytes; whole-build integration |
| Layout | partial source integration ELF; 233 symbolic vector slots/932 bytes and 86 symbolic veneers/860 bytes exact; scatter records/alignment/compressed RAM exact over 3,284 flash bytes | full startup/runtime, remaining ITCM/flash source and final image layout |
| Startup | `SystemInit` C: 546/548 bytes and four exact MMIO traces; vector helper 28/28 bytes; architectural startup/context/exception-return and proven assembly-origin scatter handlers exact, 236 bytes | final mask-test and MPU/cache code generation; C-origin runtime/library matching |
| Motor commands | 32 command/helper/init/loop bodies in C; 23 exact, 1,240/4,458 bytes in exact functions, including the complete 116-byte PI update; 56,096 PI model cases pass; reset improves to 83/110 matching bytes with 1,040 modeled cases | config, Park, motor reset, PWM, loop and timer-channel code generation; reset uses two following alignment bytes |
| Core / FlashForge | 19/20 functions exact, 410 bytes, including system reset, timer initialization and wrap support | PA action and full linking |
| GPIO | six complete C bodies, four exact functions/302 bytes | sensorless block order and peripheral setup |
| Serial | 20/22 functions exact, 972 bytes, including IRQ, initialization and reset/clock helpers; complete 23-selector clock evaluator in C | clock evaluator code generation, baud-rate block ordering and console layer |
| Base / scheduler | 41/45 functions exact, 2,548 bytes; statistics exact over 232 bytes and try-shutdown newly exact over 20 bytes; main loop, timer insertion, shutdown reporting and seven move-storage functions exact; move reset fits at 86 bytes with 66/86 matching | OID iterator, busy and queue setup/reset code generation; remaining command code |
| Protocol / console | nine complete C bodies; sendf, acknowledgement and shutdown guard exact, 78 bytes | dispatch, encode/frame, block discovery, console send/task and CRC code generation |
| Stepper | 11 complete C bodies; six exact, 524 bytes; all fit; config 31/106 matching bytes after pin truncation, 7,210 actual-stock-helper model cases and 13 self-tests pass; 1,200 loader cases pass | loader/event/config/direction/stop code generation; config remains 104 bytes; models retain explicit boundary mocks |
| Trigger-sync | 11 complete C bodies; ten exact, 752 bytes; all fit; separate callback publications and exact seven-byte field clearing | trigger command has two independent instructions reordered: 148/152 matching bytes |
| Interrupts / endstops | three motor IRQs, eight actual fault traps, timer task, ADC flag clear and two endstop handlers exact: 520 bytes; SysTick and ADC/DMA helpers reconstructed | SysTick uses four following alignment bytes; other IRQ/endstop code-generation differences |
| Motor arithmetic / hardware | four arithmetic helpers and complete 2,168-byte hardware initializer reconstructed; all 181 initializer call targets/order match; square root exact over 28 bytes with 16,672 modeled cases; DQ limiter fits with 41,984 FP/ABI model cases | three arithmetic bodies unmatched; DQ model uses stock square root, independently matched by reconstructed helper; uninitialized DMA parameter and hardware timing not proven |
| Motor angles | wrap, atan approximation and observer-velocity C bodies fit; 102-float table exact over 408 bytes | atan 599/640 bytes; wrap/velocity code-generation and FP corner cases |
| ADC SDK | 16 complete bodies covering 1,072 stock bytes; eleven exact, 826 bytes; trigger 46/46 and special selection 92/92 exact; deinit improves to 68/72 with 2,270 scratch call/ABI cases; native tests pass | five code-generation mismatches; original wide-mask spelling and hardware timing unproven |
| Digital output | nine complete queued-output/software-PWM bodies fit; three exact, 280 bytes | six code-generation mismatches; stock adds a 5 ms queue-clock clamp |
| Analog / buttons | 16 complete functions fit; nine exact, 866 bytes, including ADC sampling and DWT delay; button query improves to 98/124 with 768 scratch state/access/call cases | seven code-generation mismatches; ADC setup differs by one byte; sample-cache extent unresolved |
| Timer / DMA / interrupt control | 20 complete functions all fit; seven exact, 564 bytes; timer offset table exact, 80 bytes; 7,483 timer and 10,177 DMA/control modeled cases pass | 13 code-generation mismatches; IRQ enable now 100/102 matching bytes |
| PWM / current SDK | ten complete functions fit; seven exact, 230 bytes; channel initialization 90/98 and initializer 99/116 matching bytes; 982 modeled MMIO/call/configuration cases pass | three code-generation mismatches; SDK calls partly mocked in model |
| Trigonometry | complete sine and sine/cosine C fit; sine/cosine 452/480 bytes with 34,824 modeled cases; exact 131-float table, 524 bytes | both bodies unmatched; standalone sine FP corners and physical exception timing remain unproven |
| Configuration / JScope | full finalization and RTT configuration C; JScope initializer exact, 64 bytes; RTT constants exact, 25 bytes; 276 finalization model cases pass | finalization and RTT code-generation differences; finalization services mocked; no RTT debugger/hardware test |
| Scatter runtime | C decompressor/null plus proven assembly-origin copy/zero; null/copy/zero exact; 36 assembly-handler model cases pass; 86 C-reference cases pass | C decompressor oversized, entry now correct; copy/zero C versions retained only as semantic references; no complete boot |
| Protocol constants | ACK encoder and separate parser-error string exact, 29 bytes | no remaining currently referenced read-only data dependencies |
| GPIO output | five complete bodies fit; reset 196 bytes, toggle 112 bytes; 10,156 modeled ABI/MMIO cases exact; full-width arguments and motor pseudo-pins preserved | all five byte gates differ |
| Memory runtime | six complete C bodies; native behavior checks pass; strcmp and 18-byte memset integrated; all entries correct | four helpers still oversized and standalone-only; no memory body byte-exact |
| Initialized RAM | 16 typed state objects, 144 retained `.ctr` strings and explicit alignment; all 11,912 bytes exact; source-only encoder matches all 3,225 compressed bytes | complete runtime integration |
| Zero-initialized RAM | 49 real typed objects, 23,675 bytes, including JScope/RTT buffers and two task wake bytes | 10,301 bytes remain explicitly unclassified; ADC cache remains an incomplete external array |
| Toolchain | licensed Arm Compiler 6.20-6.23 under `work/atfe/ac6.2x/` (Keil MDK Community licence, cache in `~/.armlm`, renews weekly); 6.20 `-O1` scores 212 exact / 23.4k matching bytes against ATfE 22.1.0's 187 / 19.0k on source shaped for 22.1.0; ranking is monotone towards older releases; `-O1` beats every `-O2` variant | 6.19 and 6.18 (developer.arm.com login); move the isolated gates and canonical build to armclang `-O1`; re-shape the six bodies that only match at `-O2` |
| Whole image | `build-gd-image.py` assembles all three flash spans and compares 45,552 bytes: 14,809 differ, 1,397 of them in uncovered gaps (five microlib bodies, two undersized GPIO output bodies) | everything above; `gpio_out_write`/`gpio_out_toggle_noirq` are 846/266 bytes in stock against 230/112 in C |
| Upstream | `6d70050` is a declaration-compatible working baseline | exact source vintage and differences invisible to `.ctr` |

## Reproducible artifacts

The [C reconstruction scoreboard](recovered/README.md) gives exact code/data
extents, remaining divergences and all compiler commands. ATfE is retained at
`work/atfe/ATfE-22.1.0-Linux-x86_64`; the temporary user path is no longer needed.
Candidate global options `-mllvm -arm-promote-constant -fno-unroll-loops
-falign-loops=4 -mllvm -enable-shrink-wrap=false -fno-builtin
-mllvm -align-all-functions=1` preserve the four original
probes and all previously exact functions. Disabling shrink-wrapping fixes
three complete functions (GPIO output options, OID lookup and shutdown clear)
without regressing any of the 90 exact functions in the preceding partial link.
Disabling builtins restores the observed memory-call clobber policy in protocol
framing; a full integration comparison changed no previously integrated byte
and preserved all 103 then-exact functions. It remains a candidate compatibility
setting, not proof of stock's original compiler invocation.
The globally tested two-byte function alignment preserves all 539 preceding
partial-link sections byte-for-byte and corrects the runtime entry addresses;
it is not a per-function workaround. The square-root helper uses the original
SDK's narrow VSQRT intrinsic pattern, not business-logic assembly. Its complete
28-byte span is exact; the application's original SDK spelling remains an
inference. See [compiler/alignment recovery](notes/compiler-alignment-recovery.md).

`python3 tools/check-gd-recovery.py` runs all current reconstruction gates
and saves a machine-readable result without stopping at the first mismatch.
The MPU/cache entry additionally matches 72 modeled MMIO/barrier scenarios
with actual linked MPU helpers; JScope and scheduler handoffs are mocked.
ADC/DMA interrupt helpers pass 19,090 modeled MMIO/oracle cases with actual
linked code and no mocked calls. The last full wrapper, at the shutdown/loop-B checkpoint, reports 38/70 passing
processes; the remaining 32 byte-comparison gates fail on documented mismatches,
with no stale-report or model errors. Sine/cosine adds 34,824 modeled cases,
the independently exact square-root helper adds 16,672, and the motor-reset
model adds 1,040 cases with actual stock callees. The PI model passes all
56,096 state/FP/ABI cases and six negative provenance checks. PWM update adds
32,256 modeled MMIO/FP/ABI cases and six negative provenance checks; its full
228-byte candidate improves to 95/228 matching bytes but remains nonexact.
Motor step improves to 150/156 matching bytes at the correct 156-byte extent;
its 32,256 combined ordered-state/timer/FP/ABI cases and 13 negative provenance
tests pass. These do not establish asynchronous hardware equivalence.
The complete loop-B candidate now occupies its stock 860-byte extent and
matches 104/860 bytes. Its 37,888 ordered-state/timer/call/FP/ABI cases and
19 self-test controls pass; all external motor callees are explicit mocks.
The exact statistics update passes 1,564 modeled state/access/call/ABI cases
and 13 negative provenance tests. Move reset passes 1,656 scratch ordered-memory
cases at its corrected 86-byte extent, but remains nonexact.
It is not a complete firmware build. Do not add gate totals: original probes
overlap the core/motor source, and generated string data overlaps lookup pools.

`python3 tools/build-gd-partial.py` links current real definitions at observed
addresses. It preserves 187/281 exact C functions (11,006 complete-span bytes),
236 separately classified runtime assembly bytes, all reconstructed data,
vectors and generic symbolic veneers. Ninety-four integrated C-body mismatches,
five standalone-only oversized bodies and four external code dependencies
remain explicit; no external read-only data bindings remain, while the ADC cache
is one incomplete external RAM array. A
successful partial link is not whole-image success or a flashable artifact.
The separate partial-parity gate compares all 456 required sections with their
fresh isolated candidates, including all 281 C bodies; 87 vector/veneer
sections are explicit structural exclusions rather than independent matches.
The pin-width correction is independently linked in
`/tmp/gd-stepper-validation.WLzpFb/partial`: only nonexact `command_config_stepper`
changes among all 543 records against `/tmp/gd-shutdown-loop-final-repeat`;
all 187 exact C functions, every other exact section and initialized RAM are
unchanged, and parity remains 456/456. At the preceding shutdown/loop-B
checkpoint, canonical ELF and RAM matched the independent repeat. Only `sched_try_shutdown`
and the nonexact `mclib_control_loop_b` change against `/tmp/gd-baseline-186.json`;
all 186 prior exact C functions and every other exact section remain unchanged.
The preceding shutdown-only checkpoint independently reproduced in
`/tmp/gd-shutdown-final-repeat`. The historical statistics/reset
checkpoint independently reproduced in `/tmp/gd-stats-reset-final-repeat`, with
all 543 section records and global flags agreeing. Against `/tmp/gd-baseline-185.json`,
only `stats_update` and `move_reset` changed, preserving all 185 prior exact C functions. The historical
queue/step checkpoint (`/tmp/gd-queue-step-final-repeat`) preserved all 184
ADC/PWM matches while changing only motor step, ADC deinit, button query and
queue push. The historical ADC/PWM checkpoint independently reproduced at
`/tmp/gd-adc-pwm-final-repeat` added two ADC exacts while preserving all 182
PI-checkpoint matches; only ADC trigger/special and three PWM sections changed.
At the historical
PI checkpoint, only `mclib_pi_step` changed versus `/tmp/gd-trsync-integrated`,
preserving all 181 then-exact C functions and every other exact section.
The earlier trigger-sync batch preserves all 177 exact C functions from
`/tmp/gd-publication-repeat.EZIrL6`, changing only five trigger-sync section
hashes. The current inventory reports 45 fresh gates, zero conflicts and
28,638 unique exact runtime bytes, excluding ZI: 14,369 ITCM, 2,357 flash and
11,912 initialized RAM bytes. The 144-byte C/data overlap is unchanged.
The levelBoard binary
still matches its stock image, and its source tree is unchanged.

The same link emits `work/mainBoardGD-partial/initialized-ram.bin` from its
actual C data and linker alignment sections, with no gaps or copied stock
payload. All 11,912 expanded bytes match. The final four bytes are documented
as inferred eight-byte boundary alignment, not proof that no unused object
existed. [Scatter compression](notes/scatter-compression.md) records the generic
128-byte lexicographic-key dictionary rule that now reproduces all 3,225 bytes.
`python3 tools/build-gd-scatter.py` rebuilds RAM from the linked sections,
checks source provenance, emits semantic scatter records and computes alignment.
Its `work/mainBoardGD-scatter/scatter-data.bin` matches flash
`0x08003744..0x08004418` (3,284 bytes). Runtime helpers and the ITCM payload are
not supplied by this artifact. [Scheduler recovery](notes/scheduler-recovery.md)
records the newly reconstructed control flow and exact boundaries.
[Interrupt/hardware recovery](notes/interrupt-hardware-recovery.md) records
the new exact IRQ/endstop spans, full hardware initializer and remaining
floating-point, stack-state and code-generation caveats.
[ADC/output/runtime continuation](notes/adc-output-runtime-recovery.md) records
the next source batch, angle/protocol constants and standalone runtime models.
[Peripheral/input continuation](notes/peripheral-input-recovery.md) records
the timer/DMA/control, analog/buttons, trigonometry and PWM batches.
[Slot recovery](notes/slot-recovery.md) records exact calibration/system reset,
the newly fitting timer/stepper/DQ bodies, and the assembly-origin scatter handlers.
Their two C counterparts are explicit semantic references, not active coverage.
[Motor publication recovery](notes/motor-publication-recovery.md) records the
exact 52-byte GPIO disable, closer general reset and its real-stock-callee
model, plus four newly exact trigger-sync bodies from callback publication and
field-span clearing. [Runtime compiler provenance](notes/runtime-compiler-provenance.md)
distinguishes identical legacy-format library objects from an unproven original
compiler producer; no alternate runtime build profile has been adopted.
[PI reload recovery](notes/pi-reload-recovery.md) closes the full 116-byte
controller update through two narrowly scoped observed reads, without changing
FP arithmetic or the shared compiler settings. [ADC cache layout](notes/adc-cache-layout.md)
maps the real channel-18 store beyond the inhibit bytes without inventing an
array extent. [Runtime call boundaries](notes/runtime-call-boundary.md),
[static-lookup source shapes](notes/generated-lookup-shape.md), and
[CPU tuning diagnostics](notes/cpu-tuning-diagnostics.md) retain bounded
rejected hypotheses; none changes the current source configuration.
[ADC source shaping](notes/adc-source-shaping.md) records the newly exact
trigger and special-function helpers, including the full-width predicate
equivalence and the uncertainty about original mask spelling.
[PWM update](notes/pwm-update-recovery.md) and
[PWM initialization](notes/pwm-source-shaping.md) record closer nonexact
source and model limits. [Protocol/console shapes](notes/protocol-crc-shapes.md)
retain three rejected CRC and three byte-identical console trials.
[Queue/button publication](notes/queue-buttons-publication.md) adds the exact
40-byte common-pointer insertion tail and closer query state publication;
their scratch models pass 64 and 768 cases. [Motor step](notes/motor-step-recovery.md)
records the phase reload and ordered state accesses behind its closer body.
[Stepper pin-width recovery](notes/stepper-pin-width-recovery.md) records the
31/106-byte config result and its real-stock-helper validation. Run
`python3 tools/check-gd-stepper-config-model.py` after the stepper byte gate.
[Generated lookup permutation](notes/generated-lookup-permutation.md) records
a complete 20,000-iteration fixed-span search of the remaining static lookup
register/scheduling gap; the best score stayed at 70 and no candidate was
adopted. The lookup remains 862/932 with its 140-byte pool exact.
[Loop-B access recovery](notes/loop-b-access-recovery.md) restores observed
state publications/reloads and both directional FP subtractions; it remains
nonexact despite passing the bounded caller model.
[ADC/digital follow-up](notes/adc-digital-followup.md) retains the valid deinit
improvement and rejected digital-toggle search; [trigger shaping](notes/trsync-trigger-shaping.md)
records the completed search with no improvement to its 148/152-byte result.
[Statistics reload recovery](notes/statistics-reload-recovery.md) closes the
complete 232-byte span through the observed accumulator reload and timestamp
snapshot. [Move-reset shaping](notes/move-reset-shaping.md) records the valid
66/86-byte improvement, full-domain arithmetic argument and rejected outputs.
[Shutdown call contract](notes/shutdown-call-contract.md) closes the 20-byte
try-shutdown body through a consistently declared non-throwing callee contract;
3,614 actual nonlocal-jump model cases pass without mocked callees.
[Queue/OID shaping](notes/queue-oid-shaping.md) records two completed
20,000-iteration searches without a valid improvement.
[Runtime memory shaping](notes/runtime-memory-shaping.md) retains audited
rejected candidates without replacing C-origin runtime bodies with assembly.
[ADC setup shaping](notes/adc-setup-shaping.md) records three unchanged hand
forms and 20,000 search attempts; setup remains 219/220 matching bytes, with
1,192 bounded full-width pin/access/call cases passing and no inferred cache extent.
[Button ACK shaping](notes/buttons-ack-shaping.md) retains the completed
20,000-iteration search with no improvement; ACK remains 98/104 matching bytes.
[Atan permutation searches](notes/atan-permutation-search.md) retain the two
20,000-iteration searches and semantic rejection of a 600/640-byte candidate;
the canonical function remains 599/640 matching bytes.
Direct versus bridge calls
to excluded helpers are routed only when the extracted veneer proves the target.
[The gap audit](notes/remaining-code-map.md) classifies all 2,686 apparent code
gap bytes: vectors, veneers, scatter records and zeros consistent with alignment.
No unclassified nonzero function body remains in those gaps; source correctness
and byte equality of the already covered bodies remain separate questions.

The diagnostic global scheduler `-mllvm -pre-RA-sched=list-burr` makes both
lookups exact but is rejected as the current configuration: it regresses four
previously exact motor functions, all three exact GPIO functions and startup
(543 to 517 matching bytes). No per-function scheduler flags were introduced.

Run from the repository root:

```sh
python3 tools/extract-gd-layout.py mcu/mainBoardGD/stock/mainBoardGD.bin --out work/mainBoardGD-layout.json
python3 tools/extract-gd-generated.py --out work/mainBoardGD-generated.json
```

The layout artifact records vectors, scatter records and branch veneers.
There are 14 non-default vector targets, 159 default targets and 59 zero
slots, in addition to SP. Independent Capstone decoding agrees with all
45 flash-to-ITCM and 41 ITCM-to-flash veneer destinations.

The generated artifact records runtime addresses and raw bytes for the
50 parser slots (null slot plus 49 handlers), 18 encoder records and
their parameter types, 144 `.ctr` requests, all 32 static-string lookup
results, and the compressed/decoded identify dictionary. The identify
blob contains 1,986 compressed bytes and expands to 4,577 JSON bytes;
the decoded dictionary equals `work/mainBoardGD.dict.json`. Repeated
extraction is deterministic. Six negative checks reject corrupted parser
argument counts, parameter pointers, encoder size, identify length,
lookup opcodes and truncated input.

`extract-gd-generated.py` requires Python 3 and Capstone. Optional
`--itcm work/regions/00000000.bin --data work/regions/24000000.bin`
checks that supplied expanded files equal the regions extracted from
stock; neither tool requires the proprietary compiler.

The user-supplied open ATfE 22.1.0 compiler also passes a source probe:

```sh
python3 tools/check-gd-toolchain.py --cc /path/to/clang
```

`--cc` or `MCU_GD_CC` selects the compiler. Without either, the tool looks
under `work/atfe`, then uses the supplied `/tmp/mainboardgd-atfe.fGpsbB/`
installation if it remains present. The temporary installation is not a
durable dependency; retain the compiler elsewhere and pass its path.

| Source probe | Stock execution address | Exact bytes |
|---|---|---:|
| `timer_is_before` | `0x00005518` | 6/6 |
| `timer_read_time` | `0x00005580` | 12/12 |
| `set_hold_current` | `0x08001178` | 56/56 |
| `set_run_current` | `0x08001220` | 52/52 |

These four functions total 126/126 bytes, including literal pools, with
`-O2 -mcpu=cortex-m7 -mfpu=fpv5-d16 -mfloat-abi=hard` and separate
function/data sections. The retained source is
`recovered/toolchain-probes.c`; `work/mainBoardGD-toolchain.json` records
the compiler version/path, exact invocation, local compiler/source SHA256
and each candidate/stock byte range. The compiler hash is a local
measurement, not a comparison against a published checksum. The gate
rejects unresolved relocations in compared code sections. This is an
object-code gate for isolated source functions, not a linked firmware
layout or proof of the original compiler release.

## Findings that constrain reconstruction

- The generated encoder lookup returns null for `param_value`, although
  the compiled declarations contain it. Preserve the generated tables
  and `.ctr` as separate evidence; passing a newly generated dictionary
  alone is not a stock-equivalence gate.
- There are 32 actual static-string results, IDs 2–33. The last is
  `Not a valid ADC pin`; an unknown string separately returns 255.
  The initial interpretation of 31 matches plus a fall-through is wrong.
- `6d70050` matches the measured upstream declarations. That establishes
  a usable baseline, not the original source commit: changes that do not
  affect declarations remain invisible to this comparison.
- `SystemInit` at `0x08000620` repeatedly reloads volatile MMIO. The
  Ghidra export folds writes and incorrectly hoists status reads.
- `ctr_run_initfuncs` at `0x27c8` has 26 instruction bytes and six
  padding bytes, not the export's 268-byte body. It calls the motor init
  wrapper at `0x3d00`, which calls hardware setup at `0x08001710` and
  then initializes motor state. Preserve the observed call order; do
  not regenerate it blindly from `.ctr` declaration order.
- Motor current APIs pass their float in `s0`, use VFPv5 min/select,
  and configuration uses fused floating-point math. Ghidra's inferred
  signatures and coprocessor expressions are insufficient source.
- Resonance compensation uses harmonics 1/2/4 and is consumed by X/Y's
  control loop only. Stall detection reaches GPIO reads through motor
  state byte `+0xd2`. `mclib_identify_motor` only validates its OID.

See [startup-layout.md](notes/startup-layout.md) and
[motor-control.md](notes/motor-control.md) for the stock instruction
addresses supporting these findings.

`python3 tools/build-gd-image.py` paints the partial ELF and the scatter span
into a 45,552-byte candidate and reports the whole-image differing count, per
section and per gap. `python3 tools/sweep-gd-compilers.py label=clang ...`
repeats the partial link, scatter and image gates under several compilers
in a diagnostic overflow mode and tabulates matching bytes per function;
the retained releases are under `work/atfe/` and the result of the first
sweep is in [compiler-version-sweep](notes/compiler-version-sweep.md).
Its ELFs are not integration candidates.

## Next work and gates

0. Download Arm Compiler 6.19 and 6.18 (account needed) and rerun the sweep
   at `-O1`. Score every source change with armclang 6.20 `-O1`
   (`sweep-gd-compilers.py --no-compat --cflag=-O1 ac6.20=work/atfe/ac6.20/bin/armclang`);
   a spelling that wins only on 22.1.0 is suspect. Re-shape the six bodies
   exact only at `-O2` and drop the 22.1.0-steering idioms
   (statistics/PI/loop-B reloads) where the right compiler no longer needs them. Link the five microlib bodies from `mc_w.l`
   in the complete build rather than reconstructing library code as C.
1. Extend the now-combined generated C data, lookup and runner source into
   the complete build; close the static lookup's 70-byte register-choice
   difference. Runners preserve observed execution order, including omitted
   watchdog calls despite their retained declarations.
2. Close the remaining five oversized C-origin memory/decompression helpers
   without truncation or relocation. Extend platform/watchdog/ADC coverage and classify
   the remaining 10,301 zero-region bytes and ADC cache extent from real consumers.
3. Close code-generation differences in the recovered SDK/PWM callees and both
   complete motor control loops. Resolve timing units and mode
   bytes from their consumers; preserve floating-point/FPSCR behavior and
   existing validation. Close motor configuration and helper code generation.
4. Fit the reconstructed scatter/runtime helpers and integrate their actual
   source with the exact semantic scatter/load-data construction. Test broader
   compiler hypotheses globally against all 187 established C matches, not
   just the original probes. No per-function flags or opcode replacements.
   Isolated matches cannot identify the original compiler release.
5. Build the complete board, compare dictionaries/generated records and
   runtime layout, then pursue function and whole-image byte equality.
   Stock behavior includes the stubs and generated/source mismatch.

The compiler probe `work/ac6/AC616/bin/armclang --version` still fails
with `Failed to check out a license` and `ARMLMD_LICENSE_FILE` unset; the
sweep suggests 6.16 is in any case too old a base. Open ATfE 22.1.0 remains
the canonical gate so the established matches stay measurable, but it is not
the compiler to shape source against. No original-version or complete rebuild gate passes.
Source experiments belong in an isolated tree; the levelBoard recovery
is not the mainBoardGD build target.
