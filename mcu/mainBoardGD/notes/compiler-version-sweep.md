# The compiler is the variable: an LLVM release sweep

Session 2026-09-11. Until now every mainBoardGD gate ran on one compiler,
ATfE 22.1.0, chosen because it was the open armclang-family compiler at hand,
not because anything in the image pointed at it. The image itself says
armclang and armlink ([recon](recon.md) §8); the version was left open. This
note measures the same source under nine LLVM releases and finds that the
release moves more functions than any source spelling has.

## The whole-image gate

`tools/build-gd-image.py` did not exist before this session. It paints every
allocated section of the partial ELF into stock's three flash spans (flash
code, scatter table plus compressed RAM, ITCM payload), fills the rest with
zero, and compares all 45,552 bytes with stock. It is the `cmp -l` count the
levelBoard was driven by. First reading, with the canonical ATfE 22.1.0 build:

    Whole image: 30743/45552 bytes match stock; 14809 differ
      13412 inside recovered sections, 1397 in uncovered gaps
    Uncovered: 2444 bytes in 219 gaps, 1397 of them nonzero in stock

The positional count overweights a body whose length differs by two bytes
(everything after the shift misaligns), so for choosing a compiler the
per-function table below is the better instrument; the whole-image number
is the deliverable's gate.

The uncovered nonzero bytes are the five microlib bodies (`0x080003f4`,
`0x0800046e`, `0x080004ec`), and the tails of C bodies that are shorter than
stock's: `gpio_out_toggle_noirq` is 266 bytes in stock against 112 in the
candidate and `gpio_out_write` 846 against 230 (ITCM `0x3390`, `0x3516`).
Stock dispatches the motor pseudo-pins through `tbb`/`tbh` jump tables and
re-tests the pin after every call; the candidates use if-chains. Those two
alone account for 780 of the gap bytes and are a source-shape question that
was invisible while only the candidate's own extent was compared.

## The sweep

`tools/sweep-gd-compilers.py` runs the partial link for each compiler in a
diagnostic mode (`--diagnostic-overflow`: a body that overruns its slot is
linked in a scratch region, its callers still bind to the stock address, and
the row is marked overflow; stray `.rodata.str1.1` pools from a compiler that
does not promote constants get a scratch home too), then the scatter build and
the whole-image compare. Source, flags and stock are otherwise those of the
canonical build. `-fomit-frame-pointer` is added globally: releases before 20
default to a frame pointer on `arm-none-eabi`, and stock's `push {r7, lr}`
sites are stack-alignment pushes with no `add r7, sp`, so this is a default
correction, not a tuning flag. Releases 13-15 are pointed at their own libc
headers; 13 lacks `-falign-loops` and the elementwise builtins.

Compilers: upstream `clang+llvm-12.0.1`; LLVM Embedded Toolchain for Arm
13.0.0, 14.0.0, 15.0.2, 16.0.0, 17.0.1, 18.1.3, 19.1.5; ATfE 22.1.0. All are
retained under `work/atfe/`, with a stub `libtinfo.so.5` in `work/atfe/shim/`
so the 2021-2023 binaries load on a libtinfo6 host.

| clang | exact functions /281 | matching bytes, all functions | whole-image differing |
|---|---:|---:|---:|
| 12.0.1 | 179 | 16,888 | 17,437 |
| 13.0.0 | 180 | 18,693 | 15,595 |
| 14.0.0 | 187 | 20,122 | 14,157 |
| 15.0.2 | **189** | 20,554 | 13,735 |
| 16.0.0 | **189** | 20,398 | 13,901 |
| 17.0.1 | 187 | **20,795** | **13,560** |
| 18.1.3 | 180 | 18,555 | 15,562 |
| 19.1.5 | 182 | 18,940 | 15,145 |
| 22.1.0 (canonical) | 187 | 19,037 | 14,809 |

Every metric peaks in the 15-17 band, on source that was shaped for 22.1.0
for a year. The compatibility flags were derived on 22.1.0 too; on 13.0.0,
`-mllvm -arm-promote-constant` alone accounts for 177 of its 180 exact
functions and the other four flags for the rest, so the flag set is not what
carries the older releases.

## What moves, and which way

204 of 281 functions are exact under at least one release; 165 under all;
77 under none. The 39 version-dependent ones split cleanly:

- **Exact on 13-17 (some on 12-19), not on 22.1.0**: `ctr_lookup_static_string`
  (the 70-byte register-choice gap a 20,000-iteration search could not close),
  `command_config_stepper` (31/106 on 22.1.0), `command_set_next_step_dir`,
  `command_config_analog_in`, `console_sendf`, `gd_motor_adc_clock`,
  `gd_motor_adc_deinit`, `gd_motor_timer_deinit`, `gd_motor_timer_oc_shadow`,
  `gd_usart_baudrate_set`, `gpio_in_read`, `mclib_pwm_channel_init`,
  `mclib_timer_channel_enable`, `oid_next`, `move_queue_setup`, `gpio_adc_setup`.
- **Exact only on 22.1.0**: `analog_in_shutdown`, `analog_in_task`,
  `buttons_task`, `gd_motor_timer_init`, `mclib_current_acquisition_calibrate`,
  `mclib_gpio_enable`, `sched_add_timer`, `sched_main`, `stats_update`,
  `stepper_shutdown`, `trsync_shutdown`, `trsync_task`. Most of these carry a
  spelling introduced to steer 22.1.0 (the observed-reload and snapshot
  idioms in `statistics.c`, `pi-reload`, `loop-b-access`). On 16.0.0
  `stats_update` differs from stock by one instruction's schedule
  (`ldr r6,[r5]` before rather than after a `str`/`movw`/`movt` group), and
  `analog_in_task`, `buttons_task`, `sched_add_timer` are within six bytes.
- **Never exact, but far closer on 13-17**: `gd_motor_timer_oc_config`
  806/816 on 13-14 against 110 on 22.1.0; `mclib_control_loop_b` 408/868
  against 104; `gd_rcu_clock_freq_get` 977/1864 against 202;
  `command_dispatch` 185/328 on 16 against 24; `endstop_event` 120/146 on 16
  against 19; `gd_motor_dma_init` 165/228 against 21; `stepper_stop` 94/114
  against 23.

No single open release is the compiler: 15 and 16 lose `SysTick_Handler`
and `mclib_sine` ground that 13 holds, and none reproduces the
22.1.0-shaped bodies without their steering idioms. That is what an Arm fork
looks like from outside - Arm Compiler 6 carries its own scheduling and
backend changes on top of an LLVM base - and the base the numbers point at is
the 15-17 generation, i.e. Arm Compiler 6.19-6.21 (2022-2023), not the
AC6.16 (LLVM 12 base) that happens to be on disk unlicensed.

## Arm Compiler for Embedded, same day

The user fetched Arm Compiler 6.20, 6.21, 6.22 and 6.23 from Arm's public
artifactory (public `wget`, geoblocked here only) and activated a Keil MDK
Community licence on another host; the `~/.armlm/store` cache is bound to the
activating OS username, so it had to be activated as `shish` to unlock here.
They live under `work/atfe/ac6.2x/`; `sweep-gd-compilers.py` links their
output with the ATfE driver because armclang's driver cannot take a GNU ld
script, and supplies CMSIS 5.7.0's `cmsis_armclang.h`, which Klipper's import
omits. `board_main.c` now keeps its GCC-header barrier overrides out of the
armclang path, and `core.c` spells the irq helpers as upstream `armcm_irq.c`
does: armclang's own `__disable_irq()` intrinsic also reads PRIMASK, which
stock's 4-byte `irq_disable` does not.

Same source, same diagnostic link, armclang's own defaults plus one flag:

| armclang | flags | exact /281 | matching bytes | whole-image differing |
|---|---|---:|---:|---:|
| 6.20 | `-O2` (compat flags off) | 194 | 19,825 | 14,755 |
| 6.20 | `-O2` + ATfE compat flags | 208 | 21,819 | 12,435 |
| 6.20 | `-O2 -fno-unroll-loops` | 208 | 21,693 | 12,639 |
| 6.20 | `-O2 -fno-unroll-loops`, jump threading off (irq fix included) | 211 | 21,646 | 12,694 |
| **6.20** | **`-O1`** | **212** | **23,382** | **11,065** |
| 6.21 | `-O1` | 201 | 22,786 | 11,663 |
| 6.22 | `-O1` | 189 | 19,983 | 14,210 |
| 6.23 | `-O1` | 189 | 19,703 | 14,476 |
| 6.20 | `-Os` | 169 | 15,712 | 18,699 |
| 6.20 | `-O3` | 158 | 13,794 | 22,163 |

(The 212 row includes the three irq helpers fixed by the upstream spelling;
the same source scores 209 before that edit. `-funsigned-char`,
`-fshort-enums`, `-fshort-wchar`, `-D__MICROLIB` and `-std=c99`, the rest of
µVision's standard line, change nothing.)

Three things fall out:

- **The version ranking is monotone: older is better**, 6.20 > 6.21 > 6.22 ≈
  6.23. 6.19 and 6.18 are not on the public artifactory and need an Arm
  account to download; they are the next measurement.
- **`-O1` beats every `-O2` variant**, and not marginally: the bodies that
  no source shaping reached become exact or nearly so at `-O1` with the
  existing source - `gpio_out_write` **843/846** (its `tbh` dispatch tables
  appear on their own; the `-O2` candidate is 226 bytes), `command_dispatch`
  332/332, `command_encode_and_frame` 380/380, `console_task`,
  `analog_in_event`, `buttons_event`, `endstop_event`, `stepper_event_full`
  all exact, `gd_rcu_clock_freq_get` 202 → 1,613/1,944,
  `command_find_block` 9 → 202/232 (only r8/r9 swapped), `mclib_pwm_prepare`
  9 → 150/164. `-O1` is µVision's default optimisation level for an armclang
  project, which is where a Keil-built GD32 firmware would get it.
- **The six functions exact at `-O2` but not `-O1`** (`gpio_adc_setup`,
  `mclib_timer_channel_enable`, `USART0_IRQHandler`, `command_trsync_start`,
  `trsync_shutdown`, `oid_next`) all carry ATfE-era steering spellings
  (snapshots, observed reloads); `oid_next` in upstream's own words scores
  4/58 at `-O1`, so a natural spelling is not the answer either yet. They are
  the first candidates for re-shaping against the right compiler, and the
  `-O2`/`-O1` disagreement inside one source file (`trsync.c` has nine bodies
  exact under both) says the level is one thing, not per file.

The residue at 6.20 `-O1` is 69 nonexact bodies; the largest remain
`mclib_hardware_init` (93/2,168), `mclib_control_loop_a` (152/1,352), the
timer SDK (`slave_mode`, `input_trigger`, `oc_config`), `mclib_control_loop_b`
(402/860) and the trigonometry. Whether those are spelling or a still-older
compiler is what 6.18/6.19 will say.

## Consequences

1. **Stop shaping source against 22.1.0.** Several of the last months'
   idioms fixed a compiler that is not the target. Score every source change
   with armclang 6.20 at `-O1` (and, until they are downloaded, treat 6.19 and
   6.18 as open); a spelling that wins on 22.1.0 while losing there is
   evidence against the spelling. The retained 22.1.0 build remains the
   canonical gate only until the isolated gates are moved to armclang, so that
   the established matches stay measurable across the change.
2. **Get 6.19 and 6.18.** The ranking is monotone towards older releases and
   the public artifactory stops at 6.20; both are on developer.arm.com behind
   an account. The MDK Community licence already activated covers them.
3. **The microlib bodies are not source work.** `__aeabi_memmove`,
   `__aeabi_memset`/`memclr`/`memset`, `strcmp`, `memchr` and the LZ77
   decompressor are byte-identical to `mc_w.l` members
   ([runtime provenance](runtime-compiler-provenance.md)). The stock build
   linked them from Arm's library, as the levelBoard linked `__udivmoddi4`
   from libgcc; a complete build should do the same rather than keep
   reconstructing them as application C under a compiler Arm never used for
   them.

## Reproduce

    python3 tools/build-gd-image.py                     # whole-image gate on the canonical build
    python3 tools/sweep-gd-compilers.py --table \
        llvm-15.0.2=work/atfe/LLVMEmbeddedToolchainForArm-15.0.2/bin/clang \
        llvm-17.0.1=work/atfe/LLVMEmbeddedToolchainForArm-17.0.1-Linux-x86_64/bin/clang \
        atfe-22.1.0=work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang

Results land in `work/gd-sweep/<label>/` with `summary.json` alongside. The
sweep is diagnostic: its ELFs bind overflowing bodies at scratch addresses and
must not be mistaken for integration candidates.
