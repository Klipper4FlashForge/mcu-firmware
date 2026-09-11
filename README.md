# FlashForge MCU firmware: recovered source

The Creator 5 / 5 Pro has four motion-control MCUs behind its MIPS host,
and all four run **Klipper** — FlashForge says so themselves, in the
`license: GNU GPLv3` field their own images carry. They ship the images
and not the source.

This repository recovers that source to the standard that leaves no room
for argument: **the rebuilt image is byte-identical to the one FlashForge
ships.** Not a lookalike, not a functional equivalent — the same bytes.

| board | MCU | clock | image | status |
|---|---|---|---:|---|
| [levelBoard](mcu/levelBoard/) | N32G45x (reports `stm32f103xe`) | 128 MHz | 26,704 B | **done — 0 differing bytes** |
| [eBoard](mcu/eBoard/) | `stm32f103xe` | 144 MHz | 43,580 B | not started |
| [heaterBoard](mcu/heaterBoard/) | `stm32f103xe` | 144 MHz | 34,748 B | not started |
| [mainBoardGD](mcu/mainBoardGD/) | `gd32h757zg` | 600 MHz | 45,552 B | C recovery and isolated byte matches; full build pending |

## Verify it

    ./test/verify.sh

Builds and checks the result against the stock image: MD5, size, `cmp`,
every function address, all 54 command handlers, the data dictionary and
the identify blob. It refuses to run while `klipper/` has uncommitted
edits, so a pass describes the committed source and not the working tree.
Needs `curl`, `git`, `python3`, a host C toolchain, and ~600 MB in `work/`.

## Why a commit and not a patch

    git log --oneline klipper/
    c1ae36d Recover the FlashForge levelBoard firmware, byte for byte
    9c72499 Import upstream Klipper 6d70050, unmodified

The import commit's tree hashes to upstream's own tree object, so the
baseline is provably unedited and the recovery lifts onto a real Klipper
fork:

    git format-patch -1 --relative=klipper -o /tmp <recovery-sha>
    git -C <klipper-fork> checkout -b flashforge 6d70050
    git -C <klipper-fork> am /tmp/0001-*.patch

From there it rebases onto later upstream like ordinary work — real
history and a diff `git` computes, rather than a patch file somebody has
to remember to regenerate.

## Layout

| | |
|---|---|
| `klipper/` | upstream at `6d70050`, plus one commit: the recovery |
| `mcu/<board>/` | the account of that board, and `stock/` — the image as FlashForge ships it |
| `tools/` | analysis tools — dictionary, disassembly, scoring, permuter |
| `test/verify.sh` | the byte-exactness gate |
| `.claude/` | the skill and agents that carry the method to the next board |

## Continuing

Read [`.claude/skills/mcu-recovery/SKILL.md`](.claude/skills/mcu-recovery/SKILL.md)
— what the levelBoard job settled and must not be re-opened, the compiler
lever that closed its hard functions, and where the other boards start.
eBoard and heaterBoard are the near targets: same family, same toolchain,
everything pinned about GCC 10 transfers. `mainBoardGD` is a different job
— no GD32H7 port exists upstream, and its own image proves it was built by
armclang and armlink rather than by the GCC its dictionary names.

## Licence

The recovered source is a derivative of Klipper and is
**GPL-3.0-or-later**, the same licence FlashForge's own images declare.
The stock images under `mcu/*/stock/` are FlashForge's binaries, included
as the comparison target; they are not ours to relicense.
