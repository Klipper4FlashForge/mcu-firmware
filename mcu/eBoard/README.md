# eBoard — not started

The extruder board. With `heaterBoard`, the **near target**: same MCU
family and toolchain as the levelBoard, so everything pinned about GCC 10's
behaviour transfers directly.

| | |
|---|---|
| MCU / clock | `stm32f103xe`, 144 MHz |
| load address | `0x08010000` |
| stock image | `stock/eBoard.bin`, 43,580 B, MD5 `3a6c9ca319f81dd74b56f6a3065e80e1` |
| commands | 77 |
| toolchain | GCC ARM 10.3-2021.10, builder `DESKTOP-OQU99DN` (from `build_versions`) |

The only board with real implementations of `get_emcu_pa_value` and
`pa_action`, which drive the pressure-advance pickup.

**Open:** 144 MHz is a clock option upstream does not offer for this
family, so the clock tree has to be reconstructed before layout can be
pinned.

**Start:** `./tools/extract-dict.py mcu/eBoard/stock/eBoard.bin work/eBoard.dict.json`,
then hand it to the `mcu-board-bootstrap` agent, which pins layout before
any function matching begins. The settled facts are in
[`../levelBoard/README.md`](../levelBoard/README.md) and the skill — do not
re-open them.
