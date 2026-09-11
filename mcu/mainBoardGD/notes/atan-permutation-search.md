# Bounded atan2 source-permutation search

The canonical `mclib_atan2` remains **599/640 bytes matching**, with no C
candidate adopted. The target is the complete flash span
`0x08000890..0x08000b10`, including literals, Thumb entry `0x08000891`,
and `mclib_atan_table` bound to `0x0800338c`.

## Method and constraints

Both scratch runs use the existing local decomp-permuter, four workers,
and a seed-task stream capped at 20,000 iterations. Compiler and linker
inputs stay fixed. The extracted minimal C baseline was verified to emit
the same complete 640-byte section as the canonical candidate. Raw stock
bytes appear only in the comparison target ELF, never in candidate C.

The common ATfE 22.1.0 compilation flags are:

```text
--target=arm-none-eabi -mcpu=cortex-m7 -mfpu=fpv5-d16 -mfloat-abi=hard
-O2 -ffunction-sections -fdata-sections -Wall -Wextra -Werror
-mllvm -arm-promote-constant -fno-unroll-loops -falign-loops=4
-mllvm -enable-shrink-wrap=false -fno-builtin
-mllvm -align-all-functions=1
```

Enabled mutation weights: temporary-for-expression 100, expression
expansion 20, statement reorder 30, declaration reorder 20, assignment
split 10, commutative rewrite 15, compound assignment 10, array alias 3.
Every other weight is explicitly zero, including direct type/literal
randomization, AST deletion, dummy arithmetic and conditional-reference
tricks. No flags, register pinning, inline assembly or opcode arrays are
permitted as source solutions.

These transformations are **not a semantic safety guarantee**. In
particular, the enabled temporary-creation pass can itself randomize an
integer temporary's width or qualifiers despite disabling the dedicated
type-randomization passes. Floating-point operation order, NaN routing,
conversions, table indices and newly introduced accesses require review.
The stock-specific approximation is not interchangeable with `atan2f`.

## Runs

The first, diagnostic run used the permuter's weighted disassembly score.
It completed 20,000 iterations in 183.95 seconds: 12,583 non-error
iterations, 7,417 compile errors, no internal errors, and no saved
improvers (score 840 remained 840). This does not rule out nonexact
raw-byte gains that its heuristic failed to retain.

The second run replaces `Scorer.score` **in the scratch runner only**
with positional whole-section byte differences plus missing/extra-byte
and entry/address/symbol penalties. Size mismatches cannot score zero.
There is no instruction alignment, register normalization or ignored
literal pool. Self-tests give baseline 41, stock target 0, one-byte
growth/truncation 1, shifted section/symbol/entry 3,000,000, and wrong
ELF entry 1,000,000. Every distinct emitted-byte improvement below the
baseline is retained, not just successive best scores.

The raw-byte run completed all **20,000 iterations in 181.74 seconds**:
12,700 non-error iterations, 7,300 compile errors, zero internal errors.
Its best score was 40 rather than 41, and exactly one distinct improving
output was saved. Independent recompilation checked both full sections,
their symbol sizes, section addresses and ELF/Thumb entries: baseline
599/640, output 600/640. No tested candidate was byte-exact, and the
sole improvement fails semantic review below. Both runs exited cleanly;
execution sessions 45018 and 75931 are closed.

One retained 600/640 candidate (`output-40-1`) is invalid: it changes
`float scaled = (y * 100.0f) / x` into a chained assignment through an
`int` array element. For `x=-3.0f, y=-0.5f`, this replaces approximately
16.666666 with 16.0 before interpolation, making the fraction zero.
Its earlier floating comparison also needs exception/order review.
It is rejected, regardless of the one-byte score gain.

## Records and provenance

Temporary artifacts are retained at:

- Diagnostic run: `/tmp/gd-atan-permuter.PWIyYz/`.
- Raw-byte run: `/tmp/gd-atan-raw.ppy0ul/`.

Each directory contains frozen compiler/source inputs, `compile.sh`,
`link.ld`, `settings.toml`, target ELF/raw bytes, progress and run logs.
The raw run additionally contains `run_raw.py`, scorer self-tests,
`audit_outputs.py`, `summarize.py`, and `semantic-review.json`.
Its summary hashes all permuter Python sources, because the local
permuter at commit `6786c403af1166b507c388822685d4fcd893b282` already has
project patches in `ast_util.py` and `objdump.py`; this search does not
modify those files. `/tmp` is temporary storage, not a durable deliverable.

Input SHA-256 values:

```text
canonical mclib_angles.c
802e077546b6164366017b6eba7bbeaaff11a69ca570b2638ab5010e10ec9a31
ATfE clang-22
6df1642d4dbf2543f33966344207c34e7d6cb36cd8ef67ec4bd2a73342a74349
stock mainBoardGD.bin
9653998b1f3ba754a2ab3d045d0941b8e08c1bfa444d2f5bfc5cecaf0bab1c50
complete 640-byte stock target
3334cdf525a8596d151758bfebadb152a33f3599840d6e66490887930790ffac
```

These are finite random searches, not proofs that no matching C spelling
exists. Non-error iterations can include cached candidates and are not a
count of unique compiled programs. The random seed stream is not pinned
for exact replay. No project C, global flags or permuter package files
were changed for either run.
