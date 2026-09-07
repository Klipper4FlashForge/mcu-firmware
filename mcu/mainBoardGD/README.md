# mainBoardGD — not started

The main board, and the **hardest of the four** by a wide margin. Do the
eBoard and heaterBoard first.

| | |
|---|---|
| MCU / clock | `gd32h757zg`, 600 MHz |
| load address | `0x08000000` |
| stock image | `stock/mainBoardGD.bin`, 45,552 B, MD5 `fb64911bac422a27d7ed7fab3597603f` |
| commands | 49 |
| toolchain | GCC 7.3.1 (7-2018-q2-update), builder `ubuntu` (from `build_versions`) |

Two things make it a different job:

- **Upstream Klipper has no GD32H7 port at all.** The other boards start
  from a target that already exists; this one does not.
- **A different compiler.** The register-allocation behaviour the
  levelBoard job pinned is GCC 10's. The *method* transfers; none of the
  measured constants can be assumed to hold. Re-measure, starting with
  `objalign.py` against `__udivmoddi4` from a candidate 7.3.1 libgcc —
  that settles toolchain and multilib without compiling the firmware.

Carries five of the seven FlashForge commands (no `set_trigger_threshold`,
no `endstop_recover_state`) plus seven `mclib_*` closed-loop stepper
commands the others lack.

**Start:** `./tools/extract-dict.py mcu/mainBoardGD/stock/mainBoardGD.bin work/mainBoardGD.dict.json`
