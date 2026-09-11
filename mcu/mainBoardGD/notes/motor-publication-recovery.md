# Motor and trigger-state publication recovery

Measured on 2026-09-09 against mainBoardGD MD5
`fb64911bac422a27d7ed7fab3597603f`, using the unchanged shared ATfE configuration.
Only `recovered/mclib_commands.c` changes in the initial motor batch. The motor gate
now has 22/32 exact functions, totaling 1,124 complete-span bytes. All 21
previously exact motor sections remain byte-identical.

## Exact GPIO disable

`mclib_gpio_disable` occupies flash `0x08000b80..0x08000bb4`, 52 bytes.
It clears active/target currents and step position, resets selected observer
state, disables PWM, then publishes mode/stall/gate bytes. It does not reset
PI state, acquisition state, phase or alternate-control mode.

Stock writes timing gate `motor+0xd0` with STRB at `0x08000baa`, followed by
idle gate `motor+0xd1` with STRB at `0x08000bae`. The prior C candidate merged
them into one halfword transaction and emitted 48 bytes. These fields are also
read or written by the interrupt-driven control loops. Explicit volatile byte
views for these two publications preserve their separate access widths and
order without making the whole motor structure volatile.

The resulting function is **52/52 bytes exact**, including both calls and its
return. No header layout, compiler option, assembly body or extra memory access
is introduced. Exact target instructions establish the recovered behavior;
they do not prove that the original application used the same C spelling.

## Closer general reset

`mclib_motor_reset` has a 110-byte stock span at
`0x080011b0..0x0800121e`, followed by two zero alignment bytes before the
next function at `0x08001220`. Unlike GPIO disable, it resets phase/increment,
microstep mode, selected observer/PI state and current-offset acquisition.

The same timing/idle gate byte publications, plus the interrupt-facing mode
byte publication, improve the positioned comparison from 22/110 to 83/110
matching bytes, with a 40-byte exact prefix. The candidate is 112 bytes and
ends exactly at `0x08001220`; it uses the two documented alignment bytes.
The full section is checked, never truncated to claim a match.

The state-write sequence now agrees with stock, including the packed
phase/increment word and separate gate bytes. Threshold-constant scheduling
and the final call sequence still differ. Stock ends with BL to the acquisition
reset bridge and POP `{r4,pc}`; the candidate restores `{r4,lr}` and tail-branches
to that same bridge, costing two extra bytes. No dummy post-call access is
added to suppress that optimization. Making the microstep halfword volatile
had no further effect and was not adopted. No other compiled motor section
changes when the general-reset improvement is applied.

## Reproducible reset model

```sh
python3 tools/check-gd-motor-reset-model.py
```

The model validates the canonical motor report's source/compiler/stock/ELF
hashes, the real symbol entry, full extent and next-entry boundary. It executes
the stock or candidate reset with actual stock observer reset, PI reset, PWM
disable, timer-channel control, acquisition reset and filter initialization
bodies, including their flash/ITCM bridges. No callee is mocked. The report
records each stock callee's complete extent and SHA256.

All 1,040 cases pass: four passes over all 256 raw channel-byte values and four
mixed valid/invalid channel quartets, with deterministic arbitrary initial
state generated for every case.
Checks compare the following against stock and an independent field oracle:

- All 792 motor, 48 acquisition, 12 PWM and 256 modeled timer bytes, including
  fields that must survive reset unchanged.
- Ordered state writes, timer reads/writes, actual callee order and arguments.
- Preserved r4–r11/d8–d15, restored SP, return PC and stack guards.

The oracle preserves the filter initialization formula
`(8192 << 8) - 8192`, not simply `8192 << 8`. Output is saved in
`work/mainBoardGD-motor-reset-model.json` with content-based provenance.

Final LR is deliberately reported separately: stock leaves `0x0800121d`,
whereas the tail-call candidate leaves the harness return address
`0x10000001`. LR is caller-clobbered; both paths return to the same caller PC
with the same SP and preserved registers. This is not a claim that the two
instruction traces are identical.

This model uses stock callees, not a fully reconstructed callee graph. Timer
registers are ordinary latches, without real peripheral timing or interrupts.
Sequential matching does not establish asynchronous publication timing,
malformed-pointer safety or complete firmware bootability.

## Park-transform experiments not adopted

`mclib_park` remains 18/26 matching bytes at `0x080020b0`, with its full
26-byte extent. Swapping the D sum's source addends canonicalized to the same
instructions. Incremental expressions improved the byte count to 20/26 but
introduced fused VFMA/VFMS in place of stock's non-fused VMLA/VMLS; this is a
semantic regression and was rejected. Separating those product temporaries
again produced 14/26 bytes, also rejected.

Stock multiplication operands place sine/cosine first, while the current
compiler commutes some operand pairs and chooses a different accumulation
term. NaN-payload and rounding behavior remain part of the unresolved gate;
a numerically plausible formula is not sufficient to claim equality.

## Motor integration checkpoint and non-adopted search

At the motor-only checkpoint, the partial link preserves all 176 preceding exact C functions and other
exact sections; only GPIO disable and motor-reset hashes change in this batch.
The result is 177/281 exact C functions, totaling 10,104 complete-span bytes,
with 104 explicit integrated mismatches and the same five standalone exclusions.
All 456 partial-versus-isolated parity checks pass. The wrapper passes 33/65
gates; its remaining 32 failures are known byte mismatches, not model or stale
report errors. All 45 inventory reports are fresh and conflict-free, giving
27,736 unique exact runtime bytes excluding ZI.

The independent `/tmp/gd-publication-repeat.EZIrL6` build produces identical
ELF and initialized-RAM bytes. Initialized RAM remains 11,912/11,912 exact and
the scatter/load-data artifact remains 3,284/3,284 exact. The levelBoard binary
still matches stock and its source tree remains clean. These checks establish
regression stability, not a complete or flashable mainBoardGD firmware image.

A separate scratch atan source search completes 20,000 iterations with 7,417
compile errors and no internal search errors. Its weighted score remains 840;
that score is a search metric, not a byte count or equality result. No source
is adopted, and the canonical atan gate remains 599/640 matching bytes.

## Trigger-sync publication and field clearing

The following source batch changes only `recovered/trsync.c`, under the same
global compiler configuration. Its gate improves from 6/11 exact functions
(396 bytes) to 10/11 (752 bytes), preserving all six preceding exact spans.
The four new complete-span matches are:

| Function | ITCM entry | Exact bytes |
|---|---|---:|
| `trsync_do_trigger` | `0x5900` | 76 |
| `trsync_expire_event` | `0x5950` | 68 |
| `command_trsync_start` | `0x1e78` | 106 |
| `trsync_shutdown` | `0x59d0` | 106 |

Callback dispatch now uses a local volatile view of the released signal
record. It reads the next pointer, unlinks the record from `ts->signals`,
then snapshots the callback and clears the two record words before invoking
it. This follows stock's individual word accesses and publication order;
the shared structure layout and ABI are unchanged. It does not make all
trigger state volatile or introduce new memory accesses.

The reset helper describes the exact zeroed field span using
`__builtin_memset` and `offsetof`: seven bytes from `signals` at offset 28
through `expire_reason` at offset 34. Byte 35, the trailing OID padding, is
untouched. Stock implements this with overlapping word stores, one unaligned
at `signals+3`. The source expresses which fields are cleared, not instruction
bytes or forced transfer widths; the compiler selects those stores under the
unchanged global configuration. Inlined copies account for the newly exact
start and shutdown functions.

`command_trsync_trigger` at `0x1ee8` remains 148/152 matching bytes with the
correct complete 152-byte extent. Only the independent `MOVS r7,#0` and
`UXTB r6,r1` instructions exchange order. That observation explains the
remaining code-generation difference; it does not turn it into byte equality.
Exact output still does not establish the original application's C spelling.

## Final combined verification

The trigger-sync continuation raises the partial link to 181/281 exact C
functions, totaling 10,460 complete-span bytes, with 100 explicit integrated
mismatches and the same five standalone exclusions. All 177 preceding exact
C functions and all other exact sections are preserved against
`/tmp/gd-publication-repeat.EZIrL6`; only five trigger-sync section hashes
change. Relative to the earlier 176-function alignment checkpoint, only those
five plus GPIO disable and motor reset change, with no exact-match regression.

The wrapper passes 33/65 gates, with only the 32 expected byte-mismatch failures;
all 456 partial-versus-isolated checks pass. The 45 inventory reports are fresh
and conflict-free, totaling 28,092 unique exact runtime bytes: 13,939 ITCM,
2,241 flash and 11,912 initialized RAM, excluding ZI. The independent
`/tmp/gd-trsync-integrated` build produces byte-identical ELF and initialized-RAM
files. The levelBoard binary remains exact and its source tree clean.

The second atan search also completes 20,000 iterations, this time scoring
direct full-span bytes. Its sole 600/640-byte candidate sends the scaled
floating intermediate through an integer, destroying the interpolation
fraction: for `x=-3.0f, y=-0.5f`, approximately 16.666666 becomes 16.0.
That numeric regression rejects it; floating exception/order behavior also
needs review. No atan source is adopted: the canonical result
remains 599/640. [The search record](atan-permutation-search.md) distinguishes
both searches and their scoring from semantic validity. None of these partial
results establishes whole-image equality or a flashable mainBoardGD build.

The [current plan](../PLAN.md) records final integration and regression totals.
[Runtime compiler provenance](runtime-compiler-provenance.md) separately
documents legacy ARMCC-format microlib evidence: matching library-package
labels do not establish the original producer version or application compiler.
