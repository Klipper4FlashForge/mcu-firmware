# heaterBoard — not started

The heater/sensor board. With `eBoard`, the **near target**: same MCU
family, toolchain and builder as the levelBoard, so everything pinned about
GCC 10's behaviour transfers directly.

| | |
|---|---|
| MCU / clock | `stm32f103xe`, 144 MHz |
| load address | `0x08010000` |
| stock image | `stock/heaterBoard.bin`, 34,748 B, MD5 `a1e49e78e2eb5059f26775215ff2e3a5` |
| commands | 78 |
| toolchain | GCC ARM 10.3-2021.10, builder `zhengxiaomming` (from `build_versions`) |

The largest command set of the four, because it leaves I2C and the sensor
modules enabled where the other boards configure them out. That cuts both
ways: more of the image is plain upstream code, so it is easier to match
but there is more of it to place.

**Open:** the same 144 MHz clock option upstream does not offer.

**Start:** `./tools/extract-dict.py mcu/heaterBoard/stock/heaterBoard.bin work/heaterBoard.dict.json`,
then the `mcu-board-bootstrap` agent. Settled facts in
[`../levelBoard/README.md`](../levelBoard/README.md) and the skill.
