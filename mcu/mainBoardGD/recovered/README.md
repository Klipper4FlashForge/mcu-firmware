# mainBoardGD C reconstruction

These are reconstructed source units, isolated comparison gates and a partial
integration ELF. There is no complete mainBoardGD firmware build yet; the
assembled candidate image (`tools/build-gd-image.py`) matches 30,743 of
45,552 stock bytes. Candidate source never includes
stock executable bytes; the generated protocol data is reconstructed as typed
records, strings and the original compressed identify payload.

The available compiler is ATfE 22.1.0, copied from the user-supplied installation
to `work/atfe/ATfE-22.1.0-Linux-x86_64`. The downloaded archive's measured SHA256
is `e2e9e637bba097ba6e4bae6982883fe705ffd7e8c3a7dc876964835ef1c7a724`.
The user reports checking it against Arm's published checksum; this session
independently checks the local archive and executable behavior.

A sweep of nine LLVM releases over this source
([compiler-version-sweep](../notes/compiler-version-sweep.md)) scores
LLVM 15-17 above 22.1.0 on every metric even though the source was shaped
for 22.1.0; the stock compiler is an Arm Compiler 6 of that generation.
22.1.0 stays the canonical gate below; treat a spelling that only wins on
22.1.0 as evidence against the spelling.

The candidate **global** configuration is:

```text
--target=arm-none-eabi -O2 -mcpu=cortex-m7 -mfpu=fpv5-d16 -mfloat-abi=hard
-ffunction-sections -fdata-sections
-mllvm -arm-promote-constant -fno-unroll-loops -falign-loops=4
-mllvm -enable-shrink-wrap=false -fno-builtin
-mllvm -align-all-functions=1
```

Constant promotion reproduces the encoder lookup's local string pools.
Disabling unrolling and using four-byte loop alignment reproduce startup's
polling-loop structure. The same settings preserve all previously exact
probes and motor functions. They describe a measured candidate configuration,
not proof of the original compiler identity or settings. Disabling
shrink-wrapping was tested globally: it fixed three 72-byte functions while
preserving all 90 previously exact functions in the combined link. No
per-function compiler settings were introduced.
Disabling builtins restores stock's observed reload after the `memchr` call
in framing. A full integration test found no changes to any prior compiled
row and retained all 103 then-exact functions. This global compatibility
choice does not establish the original compiler's defaults or options.
Two-byte function alignment is also global: it preserves all 539 preceding
partial-link sections byte-identically while correcting runtime entry addresses.
It allows the 18-byte C `memset` wrapper to fit; four other memory helpers and
the decompressor remain oversized. [Compiler/alignment evidence](../notes/compiler-alignment-recovery.md)
separates this measured compatibility setting from original compiler claims.

| Source or gate | Measurement |
|---|---|
| `generated/generated.c` data | 4,536/4,536 bytes across 102 sections |
| `generated/lookup-match.c`: encoder lookup | 640/640 bytes, including 144-byte pool |
| same: static-string lookup | 862/932 bytes; pool exact, 70 code bytes differ |
| `generated/runners.c` | three runners, 114/114 bytes |
| `mclib_commands.c`: command/helper/loop gate | 23/32 functions exact, 1,240/4,458 bytes in exact functions; PI update 116/116 exact with 56,096 modeled cases; reset 83/110 matching bytes, candidate 112 bytes; 1,040 modeled reset cases pass |
| same: `command_config_mclib` | 128/196 bytes; complete size and constant pool correct |
| same: `mclib_pwm_update` | 95/228 matching bytes at the complete 228-byte extent; still unmatched; 32,256 modeled MMIO/FP/ABI cases pass |
| same: `mclib_gpio_step` | 150/156 matching bytes at the complete 156-byte extent; still unmatched; 32,256 combined ordered-state/timer/FP/ABI cases and 13 negative provenance tests pass |
| `ff_commands.c`, `core.c`, `timer.c` | 19/20 functions exact, 410 bytes in exact functions; reset exact with native DSB intrinsics |
| `gpio.c` | 4/6 functions exact, 302 bytes in exact functions |
| `serial.c`, `serial_irq.c`, `serial_vendor.c` | 20/22 functions exact, 972 bytes |
| `clock_tables.c` | 8/8 bytes of shared APB prescaler shifts, verified independently and in the partial link |
| base/debug/OID commands and scheduler/move/memory units | 41/45 functions exact, 2,548 bytes; statistics exact, 232 bytes; try-shutdown newly exact, 20 bytes; move reset 66/86 matching at its correct 86-byte extent |
| `command_protocol.c` | nine complete functions; three exact, 78 bytes |
| `stepper.c` | 6/11 complete spans exact, 524 bytes; config 31/106 matching in 104 bytes after pin truncation; 7,210 actual-stock-helper cases and 13 self-tests pass; complete 96-byte loader fits with 1,200 modeled cases |
| `trsync.c` | all 11 bodies fit; ten exact, 752 bytes; trigger command remains 148/152 matching bytes |
| `motor_irqs.c`, `timer_dispatch.c` | 12/13 functions exact, 320 bytes; UsageFault's 2-byte entry exact; SysTick fits but differs (224 versus 220 bytes) |
| `adc_interrupts.c`, `dma_interrupts.c` | four complete helpers fit; ADC flag clear alone exact, 6 bytes; 19,090 modeled MMIO/oracle cases pass |
| `endstop.c` | five complete bodies fit; config/query exact, 194 bytes |
| `mclib_math.c` | four complete bodies fit; square root 28/28 exact with 16,672 modeled cases; 128-byte DQ limiter passes 41,984 modeled cases using stock sqrt, now independently reproduced exactly |
| `mclib_hardware.c` | complete initializer: 2,166 versus 2,168 bytes; all 181 direct call targets/order match, not argument/timing equivalence |
| `mclib_angles.c` | three complete functions fit; atan 599/640 bytes; 102-float table 408/408 bytes exact |
| `adc_vendor.c` | 11/16 functions exact, 826/1,072 bytes in exact spans; trigger 46/46 and special selection 92/92 exact; deinit improves to 68/72 with 2,270 scratch call/ABI cases; native tests pass |
| `timer_vendor.c` | all 11 functions fit; 4 exact, 508/3,286 bytes in exact spans; 7,483 ordered MMIO/configuration/ABI cases pass; typed offset table 80/80 bytes exact |
| `dma_vendor.c` | six complete functions; enable/circular-enable exact, 36/446 bytes; raw configuration and inverted increment semantics retained |
| `interrupt_control.c` | three complete functions; priority grouping exact, 20/180 bytes; IRQ enable 100/102 and system routing 52/58 matching bytes; 10,177 DMA/control modeled cases pass |
| `analog_in.c` | 6/10 functions exact, 498/1,036 bytes; ADC cache allocation extent remains unresolved |
| `buttons.c` | 3/6 functions exact, 368/782 bytes; query improves to 98/124 with 768 scratch state/access/call/ABI cases; complete debounce/ACK/retransmission source |
| `mclib_trig.c` | sine/cosine 452/480 bytes and sine 248/248 bytes, both unmatched; 34,824 sine/cosine modeled cases pass; 131-float guarded table 524/524 bytes exact |
| `mclib_pwm_vendor.c` | 7/10 complete functions exact, 230/548 bytes; channel initialization 90/98 and initializer 99/116 matching bytes; 982 modeled cases pass; initialization/additional-mode source still unmatched |
| `config_finalize.c` | complete 324-byte command span; candidate 308 bytes, unmatched |
| `debug_scope.c` | JScope 64/64 bytes exact; RTT configuration 200 versus 204 bytes, unmatched; two shared constants 25/25 bytes exact |
| `digital_out.c` | nine complete functions fit; queue implementation, direct set and PWM-cycle set exact, 280 bytes |
| `runtime_scatter.c` | null entry exact, 2 bytes; decompressor standalone-only; copy/zero C bodies are uncounted semantic references; 86 modeled output/access/return cases pass |
| `scatter_handlers.S` | proven assembly-origin copy/zero helpers, 28/28 bytes exact; 36 modeled cases pass |
| `protocol_data.c` | ACK encoder and separate parser-error string exact, 29 bytes |
| `gpio_output.c` | five complete bodies fit, none byte-exact; reset 196 bytes, toggle 112 bytes; 10,156 modeled ABI/MMIO cases pass |
| `runtime_memory.c` | six complete C bodies, none byte-exact; strcmp and 18-byte memset fit the partial link; all entries correct; native behavior checks pass |
| `mpu.c`, `board_main.c` | region-enable exact, 18 bytes; board main 245/298 matching bytes with native barriers; 72 modeled MPU/cache MMIO/barrier cases pass |
| `startup_runtime.S` | six architectural assembly spans exact, 208 bytes; not counted as C functions |
| `runtime_state.c` | 49 typed NOBITS objects, 23,675 bytes; 10,301 zero-region bytes remain unclassified |
| `state.c` and explicit linker alignment | 16/16 typed objects exact, 3,337 object bytes plus 7 alignment bytes |
| `compile_time_requests.c` | 144 retained requests, 8,568 expanded RAM bytes including alignment |
| `nvic.c` | 28/28 bytes |
| `system_init.c` | 546/548 bytes; MMIO traces match all four tested scenarios |
| `toolchain-probes.c` | four original probes, 126/126 bytes |

[Shutdown call contract](../notes/shutdown-call-contract.md) records the new
20-byte try-shutdown match and 3,614 actual nonlocal-jump model cases. The
non-throwing annotation is consistent across declarations and definition;
no argument ABI or compiler flag changes.
[Queue/OID shaping](../notes/queue-oid-shaping.md) records two completed
20,000-iteration searches without a source change.
[Runtime memory shaping](../notes/runtime-memory-shaping.md) records the
audited runtime search without an adopted candidate.
[ADC setup shaping](../notes/adc-setup-shaping.md) records the unchanged
219/220-byte result after three hand trials and 20,000 search attempts;
1,192 bounded pin/access/call cases pass without inferring cache storage size.

The current setters appear in both the probe and motor gates. Local strings
appear in both the data and lookup gates. Do not add these totals as firmware
coverage. Gates linking to observed external symbol addresses do not establish
a complete linked image or validate unrecovered callees.

`python3 tools/report-gd-progress.py --out work/mainBoardGD-progress.json`
audits saved results and source hashes. The current deduplicated inventory is
11,006 bytes in entirely exact C function spans (code plus any local pools),
plus 4,663 exact ITCM data/pool bytes and 965 flash data bytes, with 144 bytes
overlapping C/data evidence, and 11,912 initialized RAM bytes.
Architectural/runtime assembly adds 236 separately classified bytes, for a 28,638-byte unique runtime
union excluding zero-initialized storage. All 45 canonical reports are fresh,
with zero evidence conflicts. The execution-region totals are 14,369 ITCM,
2,357 flash and 11,912 initialized RAM bytes. Zero-initialized storage is
reported separately and does not increase executable/load-data coverage. The inventory excludes
the separately verified scatter/load-data span; it now includes the eight-byte
platform table through its independent compiled-data gate.
The initialized RAM region has
no unchecked bytes. Typed generated data alone is 4,536 bytes; the extra 18 bytes are
known pool padding. This is execution-address coverage, not a percentage of
the compressed 45,552-byte firmware image. [The gap audit](../notes/remaining-code-map.md)
classifies all apparent nonzero gaps as vectors, bridges or scatter metadata;
the remaining zero spans have explicit alignment-inference caveats.

## Partial integration

`python3 tools/build-gd-partial.py` creates `work/mainBoardGD-partial/partial.elf`
and an address/dependency audit in `results.json`. It links actual generated,
core, motor, GPIO, serial, base/scheduler, protocol and initialized-state definitions together. The
current integrated result has 187 exact C functions out of 281 checked
functions (11,006 bytes in complete exact spans); the 94 mismatches remain
explicit. Typed data, `.ctr`, all 233 vector slots (932 bytes) and all 86
cross-region veneers (860 bytes) match their stock execution-address extents.

Veneers use one generic symbolic assembler template, replacing armlink's
three-instruction bridge construction. Undefined call references route through
those symbols when their observed targets are veneers, or when an explicitly
verified direct call reaches the same missing bridge target (including RTT's
`__aeabi_memclr` call). Real C bodies are never patched. The report records every routing operation, original
source hash and missing dependency. Stock executable bytes are comparison
input only, never candidate linker input.

`check-gd-partial-parity.py` independently compares linked sections with fresh
canonical isolated candidates, including unmatched C bodies. This catches
relocation-routing regressions without mistaking a successful partial link for
stock equality. The current run passes all 456 independently referenced
sections. Synthesized vectors and bridges are 87 explicit structural
exclusions from this parity check, not extra isolated matches.

There are still four external code targets. The ACK encoder, parser-error string,
angle/trigonometry/timer tables and RTT constants now have actual read-only
definitions. There are 49 typed zero-initialized storage objects, but the ADC
sample-cache extent is still unresolved at `0x24008b18`; it remains one explicit
RAM binding rather than an invented overlapping array. Nine external symbols name MMIO addresses
and four name architectural/link-layout constants: 18 external bindings in all.
Missing symbols are explicit
absolute dependencies, not fabricated function bodies. This ELF has no complete
startup/runtime, fully classified zero-state storage or complete image layout and must not be
flashed. The pin-width correction's separate partial build at
`/tmp/gd-stepper-validation.WLzpFb/partial` changes only nonexact
`command_config_stepper` against `/tmp/gd-shutdown-loop-final-repeat` among all
543 section records. All 187 exact C functions and every other exact section
are preserved; initialized RAM is identical and parity passes 456/456.
At the preceding shutdown/loop-B checkpoint, canonical and independent builds
produced byte-identical ELF and initialized-RAM files. Only
`sched_try_shutdown` and nonexact `mclib_control_loop_b` change against
`/tmp/gd-baseline-186.json`; all 186 prior exact C sections and every other
exact section remain unchanged. The preceding shutdown-only checkpoint
independently reproduced in `/tmp/gd-shutdown-final-repeat`.
The historical statistics/reset checkpoint independently reproduced in `/tmp/gd-stats-reset-final-repeat`,
including all 543 section records and global flags. Only `stats_update` and
`move_reset` changed against `/tmp/gd-baseline-185.json`, preserving all 185 prior
exact C sections and every other exact section. The historical
queue/step checkpoint (`/tmp/gd-queue-step-final-repeat`) preserved all 184
ADC/PWM matches while changing motor step, ADC deinit, button query and queue
push. The
historical ADC/PWM checkpoint (`/tmp/gd-adc-pwm-final-repeat`) preserved all 182
matches from `/tmp/gd-pi-exact-integrated`, changing only ADC trigger/special
and three PWM sections. At the historical PI checkpoint, only
`mclib_pi_step` changed versus `/tmp/gd-trsync-integrated`, preserving all 181
then-exact C sections and every other exact section.
The earlier trigger-sync batch preserves all 177 exact C sections from the
motor-publication checkpoint while changing five trigger-sync section hashes.
The coverage inventory keeps vectors/veneers separate
from C-function progress and does not automatically add this overlapping link.

Four memory helpers and the scatter decompressor remain explicitly standalone-only,
for five excluded bodies: `__aeabi_memmove` 78/64 bytes, `__aeabi_memset` 18/14,
`__aeabi_memclr` 6/4, `memchr` 22/20 and decompressor 128/94. All now have
the correct symbol entry. The C scatter
copy/zero alternatives are separately labeled semantic references; their
proven assembly-origin implementations are active and exact. No body is
truncated or moved to conceal a mismatch. The complete stepper loader, DQ
limiter, GPIO reset/toggle, sine/cosine, C memset and timer OC shadow/slave mode now fit their slots while remaining
unmatched. Calibration is exact over `0x3a18..0x3a5c`, before the real polarity
setter at `0x3a60`. SysTick's 224-byte
candidate fits by consuming the four alignment bytes after its 220-byte stock
span; this remains a mismatch, not an exact result. The memory gate reports
symbol-entry alignment separately from instruction differences; the global
two-byte alignment setting resolves the active runtime candidates' entry shifts.
The two unused C scatter-handler references retain two-byte leading alignment
from their loops and remain explicitly separate evidence.
The combined link now rejects any shifted function entry, not just a misplaced
output section.

The partial linker also emits `initialized-ram.bin` from actual source-built
ELF sections and linker alignment, rejecting holes or overlaps. It matches all
11,912 expanded stock bytes. Three bytes align `periodic_timer`; the final
four bytes are an explicitly documented eight-byte boundary-alignment
inference, not an invented state object. The source-only scatter compressor
now reproduces all 3,225 compressed bytes with its generic `lazy-lex128`
dictionary rule. See [compression evidence](../notes/scatter-compression.md).

`tools/build-gd-scatter.py` independently reads the linked candidate RAM
sections, checks provenance, emits the three semantic scatter records and
computes load alignment. Its 3,284-byte artifact matches flash
`0x08003744..0x08004418` exactly, with synthetic layout/round-trip tests.
It does not include runtime helper bodies or the ITCM payload.

Run from the repository root:

```sh
python3 tools/check-gd-recovery.py
```

This runs all current gates with the same global configuration and records
`work/mainBoardGD-recovery.json`. A nonzero result is expected while recorded
byte mismatches remain. The last full regression, at the shutdown/loop-B checkpoint, passes 38/70 gate processes;
the remaining 32 processes report known byte mismatches, with no model or
stale-report errors. This is not a whole-image
success. The wrapper records every invocation (including all
global options) in `work/mainBoardGD-recovery.json`. Checks whose defaults
already include that complete configuration can also be run directly:

```sh
export MCU_GD_CC="$PWD/work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang"
python3 tools/check-gd-gpio.py --out work/mainBoardGD-gpio
python3 tools/check-gd-base.py
python3 tools/check-gd-serial.py
python3 tools/check-gd-protocol.py
python3 tools/check-gd-irqs.py
python3 tools/check-gd-adc-irqs.py
python3 tools/check-gd-dma-irqs.py
python3 tools/check-gd-endstop.py
python3 tools/check-gd-math.py
python3 tools/check-gd-hardware.py
python3 tools/check-gd-adc-vendor.py
python3 tools/check-gd-adc-vendor.py --self-test
python3 tools/check-gd-timer-vendor.py
python3 tools/check-gd-timer-vendor.py --self-test
python3 tools/check-gd-timer-data.py
python3 tools/check-gd-dma-vendor.py
python3 tools/check-gd-interrupt-control.py
python3 tools/check-gd-analog-in.py
python3 tools/check-gd-buttons.py
python3 tools/check-gd-trig.py
python3 tools/check-gd-trig-data.py
python3 tools/check-gd-trig-model.py
python3 tools/check-gd-sqrt-model.py
python3 tools/check-gd-pwm-vendor.py
python3 tools/check-gd-config-finalize.py
python3 tools/check-gd-debug-scope.py
python3 tools/check-gd-debug-scope-data.py
python3 tools/check-gd-digital-out.py
python3 tools/check-gd-angles.py
python3 tools/check-gd-angle-data.py
python3 tools/check-gd-protocol-data.py
python3 tools/check-gd-scatter-runtime.py
python3 tools/check-gd-scatter-runtime-model.py
python3 tools/check-gd-scatter-handlers.py
python3 tools/check-gd-scatter-runtime-model.py \
  --isolated-report work/mainBoardGD-scatter-handlers/results.json \
  --out work/mainBoardGD-scatter-handlers-model.json
python3 tools/check-gd-stepper-load-model.py
python3 tools/check-gd-stepper-config-model.py --self-test --out work/mainBoardGD-stepper-config-selftest.json
python3 tools/check-gd-stepper-config-model.py
python3 tools/check-gd-dq-limit-model.py
python3 tools/check-gd-motor-reset-model.py
python3 tools/check-gd-pi-model.py
python3 tools/check-gd-pwm-update-model.py
python3 tools/check-gd-motor-step-model.py --self-test
python3 tools/check-gd-motor-step-model.py
python3 tools/check-gd-loop-b-model.py --self-test
python3 tools/check-gd-loop-b-model.py
python3 tools/check-gd-stats-model.py --self-test
python3 tools/check-gd-stats-model.py
python3 tools/build-gd-partial.py
python3 tools/gd_scatter_compress.py --self-test
python3 tools/gd_scatter_compress.py
python3 tools/build-gd-scatter.py --self-test
python3 tools/build-gd-scatter.py
```

The motor `--require-all` and lookup gates currently fail on the recorded
mismatches. The startup gate passes semantic scenarios and separately reports
`byte_exact: false` for `SystemInit`. It uses Unicorn 2.1.4, installed under
`work/python-deps`, and pyelftools. Its model compares every peripheral read
and write for immediate readiness, delayed readiness, varied reset bits and
oscillator timeout; it is not a timing or hardware-board test.

`tools/check-gd-motor.py` exposes `UNITS`/`CASE_UNITS` for the command, math,
reset, I/O and register helper translation units in `mclib_commands.c`.
Separate units preserve stock's real calls without per-function inlining flags. The
generated data, `lookup-match.c`, and `runners.c` now have distinct definitions
and link together with the other recovered units in the partial ELF. Remaining
Klipper/platform source, motor loops, runtime/startup and scatter loading into
one complete firmware build are still required.

Remaining source-shaping evidence:

- `command_config_mclib` has the correct six-word pool and arithmetic but
  different FP scheduling, register choices and binding-pointer store timing.
  288 dependency-respecting local/store-order variants did not improve it;
  nor did explicit elementwise FMA or simple binding-pointer rewrites.
- Static-string lookup chooses `r0` where stock uses `r1` for return values.
  Shared-exit, signed-result chain and signed-byte fallback forms did not help.
  The LLVM `list-burr` pre-register-allocation scheduler fixes both lookup
  functions completely, but regresses motor, GPIO and startup code. It is
  diagnostic evidence, not an adopted global option or per-function workaround.
- `SystemInit` differs only in its final clock-status test: stock emits
  `and r1, r1, #12; cmp r1, #12`, while this compiler selects
  the same mask followed by `cmp #9; blo` rather than `cmp #12; bne`.
  The masked field can only be 0, 4, 8 or 12. Only two bytes differ;
  all other bytes, including the relocated tail call, agree. The four MMIO
  scenarios still match.
- The remaining core mismatch, `command_pa_action`, is 26 bytes but chooses
  different argument-load/register scheduling. The full 36-byte reset function
  is exact using native DSB intrinsics; both barriers remain around AIRCR.
- GPIO mismatches remain in sensorless-read block order
  and peripheral setup. Output-options prologue placement is now exact under
  the globally tested no-shrink-wrap setting. The exact AF/mode helpers preserve
  volatile reads/writes and selected-pin masking.
- The PI update is exact over `0x080020d0..0x08002144` (116 bytes).
  Narrow volatile views preserve the post-clamp accumulator reload and the
  output-minimum load after non-fused output arithmetic; the full controller
  layout is not made volatile. All 56,096 modeled state/write/read-count,
  returned-float, FPSCR and ABI cases pass. Read counts are checked, not every
  read's ordering or asynchronous hardware timing. See [PI evidence](../notes/pi-reload-recovery.md).
  The Park transform retains its 26-byte size with different FP operands.
- `mclib_sqrt_positive` is now 28/28 bytes exact, including its zero literal.
  `arm_math_intrinsics.h` reproduces the original SDK's narrow volatile VSQRT
  interface; it supplies no business control flow, register pinning or opcode
  payload. The positivity check stays C, and no VSQRT executes for negative,
  zero or NaN inputs. The application's original SDK spelling is inferential.
  Its independent 16,672-case model passes; the 41,984-case DQ model still
  uses the explicitly identified stock callee. See [the intrinsic evidence](../notes/compiler-alignment-recovery.md).
- Motor reset is 112 versus 110 bytes, with 83 matching and a 40-byte exact
  prefix. Separate gate/mode publications preserve stock's state-write order;
  threshold setup and the final tail call still differ. Its two-byte overrun
  consumes only documented padding before `0x08001220`. All 1,040 reset model
  cases pass with actual stock callees; LR is caller-clobbered and reported
  separately from restored SP/return PC. Timer-channel enable has its full 126-byte length
  and correct volatile RMWs, but switch-block/jump-table ordering differs.
- OID allocation and lookup are exact; the iterator differs only in five
  register-encoding bytes. Timer deletion and callback dispatch match complete
  96- and 148-byte functions. Restoring upstream readb/writeb compiler barriers
  makes wake-check exact at 20 bytes. Busy-check and conditional shutdown
  helpers remain compiler code-generation mismatches.
- Baud-rate setup has the correct 204-byte size but different switch-tail
  ordering. ADC current calibration is exact at 68 bytes: its counter snapshot
  precedes the first sample, and its volatile shared flag preserves the return
  reload. The state layout and initialized bytes remain unchanged.
- The full clock evaluator covers 23 selectors and a 1,944-byte stock span,
  including jump tables and local constants. Its candidate is 1,832 bytes
  with 202 positional matching bytes. It preserves repeated MMIO reads and
  stock's inherited PLL fraction when a later fractional-enable bit is clear.
  Host smoke checks (25,601 queries against stock-derived equations) passed,
  but are not ARM-stock execution tests or proof of complete semantic equality.
- Scheduler main, timer insertion and shutdown reporting match complete
  356-, 192- and 108-byte spans. Move allocation/free and clear/empty/first/pop
  match another 106 bytes; queue push adds an exact 40-byte common-pointer
  store tail, while setup/reset still differ. Its 64 scratch
  ordered-memory/ABI cases pass. Button query's staged report publication
  improves to 98/124 matching bytes with 768 scratch state/access/call cases.
  See [queue/button publication](../notes/queue-buttons-publication.md).
  See [scheduler evidence](../notes/scheduler-recovery.md).
- Statistics now matches its complete 232-byte span, including string/padding.
  A local volatile view restores the final sum-of-squares reload; timestamp
  snapshots and equivalent wrap-test operands preserve the remaining shape.
  All 1,564 state/access/call/ABI cases and 13 negative provenance tests pass.
  See [statistics evidence](../notes/statistics-reload-recovery.md).
  [Move-reset shaping](../notes/move-reset-shaping.md) improves reset to 66/86
  matching bytes at an 86-byte extent, with all 1,656 scratch model cases
  passing. Lossless `INT64_C(1)` expressions preserve the original integer
  domain and ordered tail reloads; original source spelling remains unproven.
- Protocol pop-count pointers and arithmetic are explicitly 32-bit, matching
  stock word stores even though this compiler's `uint_fast8_t` is a byte.
  Sendf/ACK/shutdown guard are exact; dispatch/framing/block lookup, console
  send/task and CRC remain unmatched. The console retains stock's byte-only
  read of the wider receive-position object. CRC host smoke checks passed
  1,024 inputs; this is not a stock ARM execution comparison.
  [Protocol/console source trials](../notes/protocol-crc-shapes.md) reject three
  CRC shapes and three console publication/retry variants; no source is adopted.
  Separately, [button ACK shaping](../notes/buttons-ack-shaping.md) retains
  three hand forms, a countdown follow-up and a completed 20,000-iteration
  search without improvement to 98/104. Its 2,304-case scratch model passes;
  no button source is changed by that search.
- PWM preparation and hardware update cover 392 stock bytes with complete
  source, ordered volatile writes and refined state fields. Update now has the
  full 228-byte extent and improves from 77 to 95/228 matching bytes; all 32,256
  modeled MMIO/FP/ABI cases pass, including eight timer-address reads and ordered
  writes. Both bodies remain unmatched. The update model does not establish
  asynchronous load ordering or preparation/complete-loop FP equivalence.
  See [PWM update evidence](../notes/pwm-update-recovery.md).
- ADC trigger and special selection are now exact over 46 and 92 bytes.
  Special selection uses lossless unsigned-wide predicate masks while keeping
  the full 32-bit API, MMIO and separate RMWs unchanged; original mask spelling
  remains inferential. See [ADC source shaping](../notes/adc-source-shaping.md).
  [PWM initialization shaping](../notes/pwm-source-shaping.md) improves channel
  setup to 90/98 and initialization to 99/116 matching bytes with unchanged
  extents, seven preserved exact functions and 982 modeled cases; neither
  target is exact, and the model mocks some SDK calls.
- Stepper configuration now truncates both pin arguments at the observed
  caller boundary, preserving stock's byte loads despite the full-word GPIO
  API. It improves from 29/106 to 31/106 matching bytes at unchanged 104-byte
  size. All ten other stepper sections are unchanged. The 7,210-case model
  executes actual stock GPIO/clock/IRQ/direction/queue helpers; allocation and
  shutdown boundaries remain explicit mocks. It is not physical MMIO timing
  or an independent callee-source proof. See [pin-width evidence](../notes/stepper-pin-width-recovery.md).
- The static-string lookup remains 862/932 matching (140/140 pool bytes).
  Its complete 20,000-iteration fixed-span permutation search found no
  improvement; the strict 1,225-case lookup model and generated-section
  regression checks passed. See [lookup search](../notes/generated-lookup-permutation.md).
- The Z/extruder control loop now compiles to its full 860-byte stock extent,
  including the correctly placed 44-byte literal pool, with 104/860 matching
  bytes (previously 852 bytes and 68 matching). Observed state publications,
  reloads and both directional FP subtractions are restored. All 37,888
  combined ordered-state/timer/call/FPSCR/ABI cases and 19 self-test controls
  pass, preserving all 31 other motor section hashes. All external motor
  callees are explicit mocks: this is a bounded caller comparison, not full
  motor or asynchronous hardware equivalence. Register allocation, scheduling
  and branch shapes remain nonexact. See [loop-B evidence](../notes/loop-b-access-recovery.md).
- The complete X/Y loop covers 1,352 stock bytes, including embedded and tail
  pools; its candidate is 1,284 bytes. Speed control, alternate-mode hysteresis,
  direction-specific harmonics and both current-control paths are present,
  but numeric/FPSCR and store-timing equivalence remain unproven.
- GPIO direction, disable and enable hooks are exact over 6, 52 and 120 bytes.
  Step now matches 150/156 bytes at its complete 156-byte extent, preserving
  interval publication and the post-store phase reload; all 32,256 combined
  ordered-state/timer-access, FPSCR and ABI cases pass. It remains nonexact,
  with six initial register-encoding differences. No asynchronous hardware
  equivalence is inferred. See [motor-step evidence](../notes/motor-step-recovery.md).
  [GPIO and trigger-sync evidence](../notes/gpio-trsync-recovery.md) records
  full-width arguments, physical-plus-logical effects and modeled checks.
  [Motor publication recovery](../notes/motor-publication-recovery.md) records
  the disable/reset byte-store changes and rejected Park fusion experiment.
- Trigger-sync now has ten exact bodies totaling 752 bytes. A local volatile
  callback-record view preserves unlink-before-snapshot publication order;
  `__builtin_memset` describes precisely the seven-byte signals/reason field
  span, leaving OID padding untouched. The remaining trigger command differs
  only in the ordering of two independent instructions: 148/152 bytes match.
  See [publication evidence](../notes/motor-publication-recovery.md).
  Three further hand trials and a 20,000-iteration search found no improvement;
  [trigger shaping](../notes/trsync-trigger-shaping.md) records the rejected
  IRQ predicate diagnostic separately, without transferring ADC's result.
- Two 20,000-iteration atan source searches produce no adopted improvement.
  The sole 600/640-byte candidate routes a floating intermediate through an
  integer, destroying its interpolation fraction; it is rejected. The canonical gate
  remains 599/640. See [the search record](../notes/atan-permutation-search.md).
- [Architectural startup and runtime storage](../notes/runtime-recovery.md)
  records the reset/context ABI, typed zero-state coverage and MPU/cache path.
- [Peripheral and input recovery](../notes/peripheral-input-recovery.md)
  records timer/DMA/control SDK behavior, analog/button scheduling and motor
  trigonometry. Exact tables and modeled transactions do not establish complete
  numeric/FPSCR equivalence, asynchronous hardware behavior or firmware bootability.
- [Fixed-slot recovery](../notes/slot-recovery.md) records the exact calibration
  and reset functions, fitting loader/timer/DQ candidates, assembly-origin
  scatter handlers and model limits. [The remaining-code map](../notes/remaining-code-map.md)
  classifies all apparent nonzero coverage gaps without counting vectors,
  bridges or scatter metadata as recovered C functions.
- [Runtime compiler provenance](../notes/runtime-compiler-provenance.md)
  establishes identical legacy ARMCC-format objects across three library
  packages, not an exact original producer or application compiler version.
- [ADC cache layout](../notes/adc-cache-layout.md) distinguishes real channel-18
  writes beyond the inhibit flags from unproven allocation/stack boundaries.
  No extra BSS coverage is inferred. [Runtime grouping](../notes/runtime-call-boundary.md),
  [static-lookup source shapes](../notes/generated-lookup-shape.md), and
  [CPU tuning diagnostics](../notes/cpu-tuning-diagnostics.md) record rejected
  experiments without adopting local flags or weakening the byte gates.
- [ADC/digital follow-up](../notes/adc-digital-followup.md) records the adopted
  68/72-byte deinit improvement with 2,270 scratch call/ABI cases. Its 20,000-iteration
  search also produced two rejected reset-call/ID errors. A separate completed
  digital-toggle search found only an invalid 75/76-byte candidate that reverses
  duration selection; canonical digital output remains unchanged.
