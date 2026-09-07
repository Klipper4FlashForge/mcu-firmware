# eBoard — not started

The extruder board. Alongside `heaterBoard`, this is the **near target**:
same MCU family as the levelBoard, same toolchain, and everything the
levelBoard job pinned about GCC 10's behaviour transfers directly.

| | |
|---|---|
| MCU | `stm32f103xe` |
| clock | 144 MHz |
| load address | `0x08010000` |
| stock image | `stock/eBoard.bin`, 43,580 B, MD5 `3a6c9ca319f81dd74b56f6a3065e80e1` |
| commands | 77 |
| toolchain, from `build_versions` | GCC ARM Embedded 10.3-2021.10, builder `DESKTOP-OQU99DN` |

Carries the two commands no other board has a real implementation of:
`get_emcu_pa_value` and `pa_action action=%u pc=%u`, which drive the
pressure-advance pickup.

## What is already known

The seven FlashForge commands, the dictionary layout, the compiler, the
flags and the register-allocation lever are all settled by the levelBoard
job — see [`../levelBoard/README.md`](../levelBoard/README.md) and
[`../../.claude/skills/mcu-recovery/SKILL.md`](../../.claude/skills/mcu-recovery/SKILL.md).
Do not re-open them.

What is *not* settled here: 144 MHz is a clock option upstream does not
offer for this family, so the clock tree has to be reconstructed before
layout can be pinned.

## Starting

    ./tools/extract-dict.py mcu/eBoard/stock/eBoard.bin work/eBoard.dict.json

Then hand the board to the `mcu-board-bootstrap` agent, which takes it as
far as a tree with link order, `.bss`/`.data` order, vector table,
dictionary and image size pinned — all of that comes before any function
matching.
