---
name: mcu-recovery
description: The map of the FlashForge MCU firmware recovery (tools) - the levelBoard is byte-identical and done; this is what that job pinned, what is still open about its source, and how to start on the eBoard, heaterBoard and mainBoardGD. Read first for any work on the MCU firmware; invoke as /mcu-recovery <board-or-function>.
---

# MCU recovery: the map

`mcu/levelBoard/stock/levelBoard.bin` is reproduced exactly by upstream Klipper
`6d70050` plus the single recovery commit in `klipper/`:
26,704 bytes, MD5 `156366b40ccc51f5768e083fa8ead210`, zero differing
bytes, 247/247 functions and 7,093/7,093 instructions at stock's own
addresses, 54/54 handlers, dictionary and identify blob exact.
`mcu/levelBoard/notes/recovery-log.md` is the full account; `PLAN.md` is the
finished record plus the one open question. This file is the part every
agent needs in its head.

Two jobs remain. **The source's credibility on the levelBoard** (below),
and **the other three boards**.

## Paths and environment

```
export MCU_ROOT=$PWD                                   # repo root (this worktree)
export MCU_WORK=$MCU_ROOT/work
export MCU_TREE=$MCU_ROOT/klipper                      # the recovered tree, in git
export PATH=$MCU_WORK/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH
export KLIPPER_BUILD_VERSION='?-20260609_102247-zhengxiaomming'
export KLIPPER_ZLIB=$MCU_WORK/libz-classic.so
```

| what | where |
|---|---|
| stock images / dictionary | `mcu/<board>/stock/<board>.bin`, `mcu/levelBoard/stock/levelBoard.dict.json` |
| our build | `$MCU_TREE/out/klipper.bin`, `klipper.elf`, `klipper.dict` |
| the deliverable | the single recovery commit on top of the unmodified upstream import in `klipper/` |
| board config | `mcu/levelBoard/levelBoard.config` |
| decomp-permuter (pinned, locally patched) | `$MCU_WORK/decomp-permuter` (`permuter/setup.sh` recreates it) |
| permuter directories | `$MCU_WORK/perm/<function>/` (created by `permuter/newtarget.sh`) |
| experiment tree copies | `$MCU_WORK/exp/<name>/` (rsync of `$MCU_TREE`, see rules) |
| Ghidra export of stock | `work/stock-levelboard-ghidra.c` (not in git; regenerate with `tools/ExportGhidra.java`) |
| stock disassembly notes | `mcu/levelBoard/notes/eddy-sensor.md` (eddy module, address-cited) |

## Facts that are settled. Do not re-open them.

- Compiler for the three STM32F103-class boards: GCC ARM Embedded
  10.3-2021.10, named by each image's own `build_versions`; on the
  levelBoard `__udivmoddi4` from its `thumb/v7e-m+fp/softfp` libgcc is
  250/250 exact. No version hunt.
- Flags: `-O2`, `-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=softfp`,
  no LTO, `-ffunction-sections -fdata-sections`, `-fno-shrink-wrap`,
  `-ffixed-r10`. A sweep of ~380 further `-f`/`-m`/`--param`/fixed-register
  switches (`flagsweep.sh`) found nothing. The compiler is not the variable.
- Layout on the levelBoard is solved: link order, `.bss`/`.data` order,
  literal pools, vector table, dictionary, identify blob, image size.
- The levelBoard target is stable across releases: 1.9.4 differs from
  1.9.7 in three bytes, one `movw` inside `get_mcu_version` at
  `0x08004CAC` (1001 against 7091).

## The lever that closed the hard functions

GCC's IRA drops the call-clobbered registers r0-r3 from an allocno's
profitable hard-register set once the cost of preserving it across a call
exceeds that allocno's memory cost, and that memory cost is its own
frequency-weighted reference count. **The lever is how often a local is
referenced and in which block, not how long it lives.** On the levelBoard
the caller-save cost is bracketed by measurement to between 9950 and
10470, with one reference in a hot block worth 3300.

A conditional whose two arms are identical adds a reference for free: it
emits nothing, because the arms are cross-jumped after reload and the
load and compare are then deleted. For it to reach IRA at all:

- the condition must not be foldable (value-range propagation deletes a
  test the compiler has already proved);
- the store it wraps must be volatile, or GIMPLE tail-merge removes the
  conditional first;
- both arms must be textually identical.

The other levers, all proved on the levelBoard: return placement (the
gimplifier's early-return prediction), statement order where
tree-ssa-sink could move a store, SSA first-use order, `volatile`
qualifiers deciding store order, signedness of a local (a signed
intermediate keeps its own conversion in the tree and reorders IRA's
allocnos), and how far ahead of its use a field is read.

## The open question on the levelBoard

Six identical-armed conditionals sit in the tree: four in
`ff_eddy_check_trigger`, one in `ff_eddy_update`, one in `DMA_Init`.
`gpio_out_reset` and `ff_eddy_rebaseline` needed none. One is a
believable slip; six is not. **The recovered tree reproduces stock's bytes
without being stock's source.** Two measurements say real code is missing rather
than a spelling: dropping the hysteresis-tail conditional changes
`ff_eddy_check_trigger` from 264 bytes to 268, which no register choice
can do; and stock's two range checks use opposite register pairs
(`0x08007CB6` against `0x08007CD0`) where one source shape written twice
gives the same form both times.

The candidates under investigation are the three write-only globals
`ff_eddy_last_dev`, `ff_eddy_dbg_baseline` and `ff_eddy_offset`, which
look like the residue of telemetry or debug statements, and the
`value - 1 > 0xfffe` range-check idiom, which is not how the constant
would be written by hand. `PLAN.md` carries the ruled-out list; do not
retry anything on it.

Any replacement must keep the image byte-identical. That is now the gate:
a candidate that is more believable but changes one byte is a
regression.

## The other three boards

| board | MCU | clock | load addr | image | commands | toolchain / builder |
|---|---|---|---|---:|---:|---|
| levelBoard | N32G45x (reports `stm32f103xe`) | 128 MHz | `0x08004000` | 26,704 B | 54 | 10.3-2021.10, `zhengxiaomming` |
| eBoard | `stm32f103xe` | 144 MHz | `0x08010000` | 43,580 B | 77 | 10.3-2021.10, `DESKTOP-OQU99DN` |
| heaterBoard | `stm32f103xe` | 144 MHz | `0x08010000` | 34,748 B | 78 | 10.3-2021.10, `zhengxiaomming` |
| mainBoardGD | `gd32h757zg` | 600 MHz | `0x08000000` | 45,552 B | 49 | GCC 7.3.1 (7-2018-q2-update), `ubuntu` |

The eBoard and heaterBoard are the near targets: same family, same
toolchain, and the compiler behaviour pinned above transfers directly.
The heaterBoard was built on the same machine and by the same engineer
as the levelBoard, so its habits carry; the eBoard's 1.9.7 image was
built on a different machine (the 1.9.4 one was not), which is worth
checking before assuming the environment is identical. Both need a
144 MHz clock option upstream does not offer for this family.

`mainBoardGD` is a different job: GCC 7.3.1 on Ubuntu, a GD32H7 port
upstream does not have at all, and no shared toolchain evidence with the
other three. Nothing measured on the STM32 boards transfers to it.

**Evidence from one board does not transfer to another.** The four are
not on one upstream base: eBoard carries the multi-bus `config_lis2dw`
that upstream introduced 2024-10-17, heaterBoard still has the
two-argument form that predates it, despite being built three weeks
earlier. Establish each board's own base from its own dictionary.

## Starting a new board

The levelBoard's order of work is the template, and each step gates the
next. Do not skip forward: a code score means nothing until the
dictionary matches.

1. `extract-dict.py` the stock image; find an upstream commit that
   reproduces the dictionary exactly (`compare-dict.py`). This also
   pins where FlashForge's own commands sit in the source, because
   Klipper assigns message ids from `.ctr` order.
2. Pin the version stamp and classic zlib, or nothing is reproducible
   against itself. `build.sh` shows how.
3. Settle the toolchain with `objalign.py` against a libgcc
   `__udivmoddi4`, before compiling any firmware.
4. Get the layout: link order (`linkorder.py`), section order, vector
   table (`vtcmp.py`), image size. Every function should reach stock's
   own address before any function is scored.
5. Only then per-function work: `relocmap.py --all --limit 0` to list
   what differs, then `fncmp.py`/`lcscmp.py` on one function, an
   asm-level reading of why, a shaped hypothesis, and the permuter when
   hand attempts stall.

The step agents in `.claude/agents/mcu-*.md` each own one part of that:
`mcu-board-bootstrap` for steps 1-4, `mcu-scorer`, `mcu-asm-analyst`,
`mcu-source-shaper`, `mcu-permuter` and `mcu-scribe` for step 5 and the
record.

## Hard rules

- **`$MCU_TREE` is tracked by git now, and it is the deliverable.** It is
  built in place; `out/` and `.config` are gitignored, so
  `git status --porcelain -- klipper` shows real source edits and nothing
  else. Use that as the check that a tree is clean. Iterate with
  `make -C $MCU_TREE -j2` and the environment above; `build.sh` and
  `test/verify.sh` are for gating, and `verify.sh` refuses a dirty tree by
  design.
- **Experiments happen in copies.** `rsync -a --delete $MCU_TREE/ $MCU_WORK/exp/<name>/`
  then edit and `make -C $MCU_WORK/exp/<name> -j2`. Score with
  `MCU_TREE=$MCU_WORK/exp/<name>`.
- **Never `pkill -f`.** It matches the calling shell and kills the session.
  Kill by PID from `pgrep -f permuter.py` after reading the list.
- **Jobs are 1 or 2 for make, 4 for the permuter.** The machine has 15 GiB
  and the build was tuned to that; `build.sh` refuses more.
- **Do not touch the compiler, the flags, the linker script or the Makefile
  to make one function match.** Matching decompilation done by tools finds
  "solutions" like register pinning or flag tweaks; they are wrong here
  because the rest of the image proves the configuration.
- **A candidate that matches by changing meaning is not a candidate.**
  The permuter games the metric: widened types, dropped stores, removed
  volatile. Read each one.
- **Git is the user's own.** Leave finished work in the working tree and
  say what you changed; do not commit, amend or push unless asked. There is
  no patch file to regenerate any more -- the diff *is* `git diff`, so
  there is nothing that can silently fall out of date.
- **The upstream import commit is never edited.** Its tree hashes to
  upstream's own tree object, which is what lets the recovery commit be
  lifted onto a real Klipper fork with
  `git format-patch -1 --relative=klipper`. Anything that touches the
  baseline destroys that property.
- **One board, one commit.** A win on the levelBoard amends the existing
  recovery commit rather than stacking a fixup on it -- when the user asks
  for it. A new board is its own commit.

## Tools in `tools/`

| tool | use |
|---|---|
| `fncmp.py <sym> <stock-addr> [-v] [--size N]` | positional instruction compare, prefix length, then a raw-byte `BYTES n/size` line over the `nm -S` range; `EXACT` needs both, `INSTR-EXACT POOL-DIFF` means only literal-pool words differ (`-v` lists them) |
| `lcscmp.py <sym> <stock-addr> [-v] [--size N]` | longest-common-subsequence compare with the same `BYTES` line and verdicts; `-v` prints the alignment ops |
| `cmpfuncs.py` | the 54 command handlers gate, and the `norm()`, path resolution (`MCU_TREE`, overridable by `OURS_ELF`/`OURS_BIN`/`OURS_DICT`) and byte comparator every comparator shares |
| `relocmap.py --all --limit 0` | every function: ours vs stock address, exact or `CODE-DIFF`. Grepping for `CODE-DIFF` also matches its own summary line; read the count, not the line count |
| `imgdiff.py`, `objalign.py`, `linkorder.py`, `vtcmp.py` | layout diagnostics |
| `flagsweep.sh <copy> <flags...>` | one line per flag set; needs `$(XFLAGS)` appended to CFLAGS in the copy |
| `permute.py` | older in-tree variant runner (one function, a list of spellings); superseded by the permuter but still works |
| `permuter/newtarget.sh <fn> <addr> <size> <src>` | builds `base.c`, `target.o`, `compile.sh`, `settings.toml`, prints the base score |
| `extract-dict.py`, `compare-dict.py <ours.dict> <stock.json>`, `compare-blob.py <out-dir> <stock.bin>` | dictionary and identify-blob gates |
| `ExportGhidra.java` | headless Ghidra decompile of a whole image |

Permuter settings go under `[weight_overrides]`. A `[weights]` table is
silently ignored, which is how earlier rounds ran with
`perm_var_cond_block` disabled while appearing tuned. And its
alignment-tolerant score rewards a candidate that grows a function, which
is wrong for a fixed-size one: drive those searches off a direct byte
compare against stock and use the permuter only for transformation ideas.

## Driving it as a skill

`/mcu-recovery <function>`: run the per-function loop for that function
and stop when it is `EXACT` and the whole-image `cmp -l` count fell by
exactly that function's contribution, or when three shaped hypotheses and
one permuter run of at least 20,000 iterations have not moved it. On the
levelBoard the count must stay at 0.

`/mcu-recovery <board>`: run "Starting a new board" from step 1, and stop
at the first gate that does not pass. Report the gate and what it showed.

Either way, record the numbers and what was learned in `PLAN.md`.
