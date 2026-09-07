# heaterBoard — not started

The heater/sensor board. Alongside `eBoard`, the **near target**: same MCU
family as the levelBoard, same toolchain and same builder, so everything
the levelBoard job pinned about GCC 10's behaviour transfers directly.

| | |
|---|---|
| MCU | `stm32f103xe` |
| clock | 144 MHz |
| load address | `0x08010000` |
| stock image | `stock/heaterBoard.bin`, 34,748 B, MD5 `a1e49e78e2eb5059f26775215ff2e3a5` |
| commands | 78 |
| toolchain, from `build_versions` | GCC ARM Embedded 10.3-2021.10, builder `zhengxiaomming` |

Its 78 commands are the largest set of the four, because it leaves I2C and
the sensor modules enabled where the other boards configure them out.

## What is already known

Settled by the levelBoard job and not to be re-opened: the seven FlashForge
commands, the dictionary layout, the compiler, the flags, the
register-allocation lever. See [`../levelBoard/README.md`](../levelBoard/README.md)
and [`../../.claude/skills/mcu-recovery/SKILL.md`](../../.claude/skills/mcu-recovery/SKILL.md).

Not settled here: the same 144 MHz clock option upstream does not offer for
this family, and the larger enabled-module set means more of the image is
plain upstream code — which cuts both ways, since it is easier to match but
there is more of it to place.

## Starting

    ./tools/extract-dict.py mcu/heaterBoard/stock/heaterBoard.bin work/heaterBoard.dict.json

Then the `mcu-board-bootstrap` agent, which pins layout before any function
matching begins.
