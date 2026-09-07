# mainBoardGD — not started

The main board, and the **hardest of the four** by a wide margin.

| | |
|---|---|
| MCU | `gd32h757zg` |
| clock | 600 MHz |
| load address | `0x08000000` |
| stock image | `stock/mainBoardGD.bin`, 45,552 B, MD5 `fb64911bac422a27d7ed7fab3597603f` |
| commands | 49 |
| toolchain, from `build_versions` | GCC 7.3.1 (7-2018-q2-update), builder `ubuntu` |

Two things make it a different job from the other three:

- **Upstream Klipper has no GD32H7 port at all.** The other boards start
  from an upstream target that already exists; this one does not.
- **A different compiler.** GCC 7.3.1, not 10.3-2021.10. The
  register-allocation behaviour the levelBoard job pinned is GCC 10's, and
  none of it can be assumed to hold here. The *method* transfers; the
  measured constants do not.

It carries five of the seven FlashForge commands — it lacks
`set_trigger_threshold` and `endstop_recover_state` — plus seven
`mclib_*` closed-loop stepper commands the other boards do not have.

## Before starting

Read [`../levelBoard/README.md`](../levelBoard/README.md) and
[`../../.claude/skills/mcu-recovery/SKILL.md`](../../.claude/skills/mcu-recovery/SKILL.md)
for the method. Treat every GCC-10 number in them as unverified here, and
re-measure — starting with `objalign.py` against `__udivmoddi4` from a
candidate 7.3.1 libgcc, which settles the toolchain and multilib without
compiling the firmware at all.

Do the eBoard and heaterBoard first.

## Starting

    ./tools/extract-dict.py mcu/mainBoardGD/stock/mainBoardGD.bin work/mainBoardGD.dict.json
