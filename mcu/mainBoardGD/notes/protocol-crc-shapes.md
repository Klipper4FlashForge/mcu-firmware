# Protocol CRC source-shape investigation

Measured 2026-09-09 under the unchanged shared ATfE 22.1.0 configuration.
No source or compiler option is adopted. All three existing protocol matches
remain exact: ACK 12 bytes, sendf 52 bytes and shutdown guard 14 bytes.

The complete source is `recovered/command_protocol.c`; its three translation
units preserve the protocol, console and CRC call boundaries. The baseline
full-span gate reports:

| Function | ITCM start | Candidate / stock bytes | Positional matching bytes |
|---|---|---:|---:|
| `command_dispatch` | `0x1070` | 324 / 332 | 24 |
| `command_encode_and_frame` | `0x11e0` | 364 / 380 | 44 |
| `command_find_block` | `0x15a8` | 228 / 232 | 9 |
| `command_send_ack` | `0x1c98` | 12 / 12 | 12, exact |
| `command_sendf` | `0x1ca8` | 52 / 52 | 52, exact |
| `console_sendf` | `0x2050` | 132 / 130 | 79 |
| `console_task` | `0x20d8` | 136 / 134 | 56 |
| `crc16_ccitt` | `0x2160` | 52 / 60 | 29 |
| `sendf_shutdown` | `0x4518` | 14 / 14 | 14, exact |

## Why CRC is the bounded target

Stock CRC occupies `0x2160..0x219c`, including its internal loop-alignment NOP.
It has no external call or literal pool. Its first 16 bytes agree with the
baseline, including the zero-length return and `0xffff` initial value. The
observed length argument remains a full word; it is not changed to ATfE's
byte-sized `uint_fast8_t` merely because upstream uses that typedef.

The stock loop starts at `0x2170` by zero-extending the current CRC into ip.
It reads the next byte at `0x2174`, decrements the remaining count, folds the
byte through XORs, and truncates that result to a byte at `0x2182`.
The tail constructs these two integer expressions separately:

```text
high = (data << 8) | (previous_crc >> 8)
low  = (data << 3) ^ (data >> 4)
crc  = low ^ high
```

The ordinary upstream-derived C instead produces a `UBFX` of CRC bits 8–15
at `0x217a`, without the early `UXTH`, then combines shifted operands into
fewer instructions. This is a concrete integer-expression/instruction-selection
difference, not missing CRC table data or an inferred library call.

## Three rejected source hypotheses

Scratch sources, isolated objects, complete linked ELFs and gate reports are
in `/tmp/gd-protocol-crc.advpIe`. Temporary files are diagnostic artifacts, not
the source deliverable. Each candidate builds all nine functions with the
same flags, exact stock entry addresses and unnormalized section-byte gate.

| Hypothesis | Candidate bytes | Matching bytes | Result |
|---|---:|---:|---|
| Baseline upstream-style expression | 52 | 29/60 | retained |
| Explicit `high`, `low`, then `low ^ high` grouping | 56 | 28/60 | rejected |
| Word-sized accumulator with explicit 16-bit previous-CRC snapshot | 62 | 6/60 | rejected |
| Word-sized input temporary with explicit final byte mask | 58 | 2/60 | rejected |

The first hypothesis reproduces the stock's three-instruction XOR tail, but
still uses the shifted-operand OR and middle-loop `UBFX` instead of the early
`UXTH`. Closer length and recognizable local arithmetic do not compensate for
the lower full-span score. The accumulator-width hypothesis exceeds the stock
span. The input-width hypothesis also loses instruction agreement. None
justifies replacing the current source.

All eight non-CRC candidate section hashes are identical to baseline in all
three trials, including the three exact functions. No new execution-equivalence
claim is needed for a rejected candidate; this round does not replace the
existing native CRC checks with a stock-model-only success.

## Adjacent targets and constraints

The console comparison exposes separate, concrete remaining differences.
In `console_sendf`, ATfE assigns the transmit-position and transmit-maximum
addresses to r7/r9 opposite to stock. The resulting byte-load/store encodings
account for much of its 132-versus-130-byte difference. In `console_task`,
ATfE branches directly from successful dispatch into input removal, whereas
stock repeats the `ret != 0` test; copied/remaining byte counts also occupy
different registers. These are possible future source-shape targets, not
changes adopted in this round.

## Console state-access follow-up: three rejected hypotheses

The follow-up audit finds no missing shared-state reload analogous to the PI
controller fix. `console_sendf` already reads transmit position and maximum in
stock order, publishes maximum zero before compaction, reloads position after
that publication (`0x209a..0x209e`), and publishes the compacted position and
maximum before enabling TX. The upstream `READP` macro is a plain dereference
on this platform, not evidence for an additional volatile encoder-field read.
The receive loop already preserves the low-byte position reads, retry after
an IRQ race, and final halfword publication to the wider position object.

Three independent scratch spellings tested these observed boundaries without
adding a state read or changing the retry behavior:

| Hypothesis | Stock evidence | Result |
|---|---|---|
| Assign local `copied = needcopy` after `sched_wake_tasks()` | stock commits the local register at `0x2132`, after the call | identical to baseline |
| Publish `receive_pos` through a volatile `uint16_t` view | stock halfword store at `0x2146`, before IRQ restore | identical to baseline |
| Express the retry as an explicit successful-commit branch | stock equality branch at `0x213e` enters publication | identical to baseline |

All nine complete candidate section hashes equal baseline in every trial;
the baseline independently equals all nine canonical hashes. Thus console
send remains 132 bytes with 79/130 matching, console task remains 136 bytes
with 56/134 matching, and the three exact protocol functions remain 78 bytes.
No qualifier, branch rewrite or post-call assignment is adopted. The result
does not rule out a source-context explanation for register allocation, but
does not justify inventing extra volatility or state accesses to obtain one.
No permutation run was started for this follow-up.

Scratch sources and reports are in `/tmp/gd-console-shapes.Hsx0oF`; its
`check.py` accepts `baseline`, `post_wake`, `publish_halfword`, or
`commit_branch` and the ordinary `--out` option. The directory is diagnostic,
not a durable build dependency. The descriptions above retain the rejected
transformations even if those temporary files are removed.

## Remaining constraints and reproduction

The CRC early extension does not by itself justify a volatile local or a
single-instruction assembly shim: unlike shared controller state or the
documented Arm square-root intrinsic, this accumulator is an ordinary local
integer with no observed external writer. Retain actual C and the global
configuration. A later hypothesis must explain the early narrowing and the
arithmetic grouping without dummy operations, register pinning, changed CRC
results, or per-function options. These three failures do not establish that
no exact source spelling exists.

Reproduce the canonical gate from the repository root:

```sh
python3 tools/check-gd-protocol.py
```

To rerun a retained scratch candidate, its `check.py` takes one of `baseline`,
`regroup`, `widecrc`, or `inputwide`, followed by the ordinary `--out` option.
The gate's nonzero exit remains expected because six functions are unmatched.
