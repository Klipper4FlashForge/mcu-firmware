# levelBoard — byte-identical

Upstream Klipper `6d70050` plus the single recovery commit in `klipper/`
reproduces `stock/levelBoard.bin` exactly — all 26,704 bytes.

| gate | result |
|---|---|
| differing bytes (`cmp -l`) | **0 of 26,704** |
| image size | **26,704 B**, no synthetic padding |
| functions instruction-exact at stock's address | **247 of 247** (7,093 of 7,093 instructions) |
| command handlers instruction-identical | **54 of 54** |
| vector-table slots disagreeing | **0 of 72** |
| literal pools disagreeing | **0** |
| data dictionary / identify blob | 5,663 B / 2,281 B, both exact |

Memory map is stock's: load `0x08004000` behind a 16 KiB bootloader,
initial SP `0x20004000`. The target is stable across releases — 1.9.4
differs from 1.9.7 in three bytes, one `movw` in `get_mcu_version`.

## Build and check

    ./build.sh        # build only
    ./test/verify.sh  # build, then every gate above

`verify.sh` refuses to run while `klipper/` has uncommitted edits, so a
pass describes the committed source. The result was also confirmed the
long way round: lifting the recovery commit onto a separate clone of
upstream at `6d70050` with `git am` gives the same image.

## Why this was tractable

Klipper stores its data dictionary — every command, response, config
constant and pin enumeration — zlib-compressed inside the image, so the
wire protocol comes out without disassembling anything:

    ./tools/extract-dict.py mcu/levelBoard/stock/levelBoard.bin

Against that dictionary the FlashForge delta is small. Of levelBoard's 54
commands **47 are stock upstream Klipper**; only seven are FlashForge's,
and the same seven appear on all three STM32 boards:

| command | what it does |
|---|---|
| `get_mcu_version` | reports three hard-coded constants |
| `set_trigger_threshold` | eddy trigger threshold |
| `get_basic_param` | re-baselines the eddy sensor, reports value and drift |
| `remove_peel` | snapshots the live reading, reports the last peel value |
| `get_emcu_pa_value` | pressure-advance reading — **eBoard only** |
| `pa_action` | drives the PA pickup — **eBoard only** |
| `endstop_recover_state` | re-arms an endstop after homing |

## The base

| | |
|---|---|
| upstream commit | `6d70050261ec3290f3c2e4015438e4910fd430d0` (v0.12.0-256, 2024-06-18) |
| toolchain | GCC ARM Embedded 10.3-2021.10 — named by the image's own `build_versions`, not guessed |
| target | `MACH_N32G452` — Nations N32G45x, which is why the image says `stm32f103xe` at 128 MHz |

`6d70050` is a working base, not an identification: it reproduces the stock
dictionary exactly and sits inside the date bracket, but any commit that
reproduces the dictionary would serve. The four boards are **not** all on
one base — eBoard carries a `config_lis2dw` form upstream introduced in
October 2024 that heaterBoard, built three weeks earlier, predates.
Evidence from one board does not transfer to another.

## The reservation

The recovered source carries six conditionals whose two arms are
identical. Each emits nothing — the arms are cross-jumped after reload —
and exists only to add a reference to a value, which is what moves GCC 10's
register allocator onto stock's choice. Four are in
`ff_eddy_check_trigger`, one in `ff_eddy_update`, one in `DMA_Init`.

One such construct is a believable slip; six is not. **The tree reproduces
stock's bytes without being stock's source.** Real code we have not
recovered probably supplies those references as a side effect.
[`PLAN.md`](PLAN.md) carries the evidence, the candidates and the
ruled-out list.

## More

| | |
|---|---|
| [`PLAN.md`](PLAN.md) | the finished record and the open question |
| [`notes/recovery-log.md`](notes/recovery-log.md) | the long-form account: what was pinned, which compiler behaviours decided layout, what was ruled out |
| [`notes/eddy-sensor.md`](notes/eddy-sensor.md) | the eddy module's semantics, cited by stock address |
| [`../../tools/README.md`](../../tools/README.md) | what each analysis tool does |
