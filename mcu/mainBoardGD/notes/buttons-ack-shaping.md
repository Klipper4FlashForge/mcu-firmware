# Button ACK: remaining instruction scheduling

Measured 2026-09-09 under the unchanged shared ATfE 22.1.0 configuration.
`command_buttons_ack` occupies ITCM `0x0bb8..0x0c20`, 104 bytes, with no
literal pool. It remains **98/104 matching bytes** after three initial hand
hypotheses, one stock-directed follow-up and a completed 20,000-iteration
search. No canonical source or compiler option is changed by this pass.

All six canonical button section hashes remain unchanged, including the
three exact functions (368 bytes) and the earlier query-publication improvement
to 98/124. That adopted work is described in
[queue/button publication](queue-buttons-publication.md).

## Address-level difference

Only the order of two independent loop-setup instructions differs:

```text
address  stock                    candidate
0bea     uxtb.w r2, ip             adds r0, r5, r4
0bec     [second half of UXTB]     uxtb.w r2, ip
0bee     adds r0, r5, r4           [second half of UXTB]
```

Stock narrows the pending count into its word-sized trip counter before
forming the copy source's base address. Both variants reach the same setup
at `0x0bf0`, the loop starts at `0x0bf8`, and every later byte agrees. The
internal alignment NOP at `0x0bf6` is included in every comparison.

The observed behavior is more specific than copying bytes. The full argument
word is read at `0x0bcc`, with its low byte used as the acknowledged count.
ACK count wraps through a byte store at `0x0bd4`, before disabling interrupts
at `0x0bd6`. Report count is then read at `0x0bdc`. If acknowledged count is
at least report count, stock clears report count and publishes retransmit
state `0xfe`. Otherwise it copies pending report bytes forward and publishes
the reduced count. Both paths restore interrupts through `0x3888`.

## Rejected hand forms

Each hypothesis compiles the complete button module with fixed flags and
observed symbol/callee addresses, then checks all six full spans.

| Form | Candidate bytes | Matching bytes / 104 |
|---|---:|---:|
| Canonical indexed loop | 104 | 98 |
| Byte countdown with guarded source/destination cursors | 96 | 40 |
| Word-sized pending snapshot, byte countdown and cursors | 100 | 40 |
| Reverse-count indexed loop | 100 | 40 |
| Follow-up: word countdown initialized from byte pending value | 90 | 39 |

All five non-target section hashes remain unchanged in the initial trials.
The byte-countdown forms introduce a per-iteration narrowing test, whereas
stock uses one `UXTB` followed by word-sized `SUBS/BNE`. This motivates the
single word-countdown follow-up: decrementing a positive initial byte value
cannot wrap a word counter. That form removes the repeated narrowing but
still loses stock's complete code shape. It is rejected, not adopted merely
because it is smaller. All four alternatives pass an 81-case behavioral smoke
screen, but none improves the byte gate.

## Completed raw-byte search

The isolated minimal typed C input is independently compiled and verified
identical to all 104 canonical bytes before searching and again afterward.
Its struct layout, callback declarations and raw-count ABI are unchanged.
The frozen linker script resolves each call to the observed stock target.
Stock bytes occur only in the comparison target, never candidate source.

The objective includes all positioned bytes, complete section/symbol size,
section placement, Thumb symbol and ELF entry. Negative controls score one
for growth/truncation, 1,000,000 for a wrong entry, and 3,000,000 for jointly
shifted section/symbol/entry; the exact comparison target scores zero and the
baseline scores six. No normalization or ignored alignment is used.

One worker completes **20,000 iterations in 552.066 seconds**, with **2,607
compile-error iterations**, 17,393 non-error iterations and **zero internal
errors**. No improving output is saved; the best raw score stays six. Session
93522 exits successfully and its worker is released. The search is not stopped
early on an intermediate result or restarted with more workers.

The enabled transformations are expression temporaries/expansion, declaration
and statement ordering, split/compound assignments, commutative rewrites and
array aliases. Dedicated type/literal mutation, deletion, dummy arithmetic and
conditional-reference tricks are disabled. Temporary creation can still change
types or meaning; this configuration does not certify candidates as safe.
The finite randomized run does not prove no matching C spelling exists.
Non-error iterations may include cached candidates, and the random seed stream
is not pinned for exact replay.

## Ordered-access and IRQ-boundary model

Scratch sources, model, frozen compiler/link inputs, scorer controls and final
progress record are retained under `/tmp/gd-buttons-ack.dwyOuM/`. They are
temporary diagnostic artifacts rather than firmware build dependencies.

```sh
python3 /tmp/gd-buttons-ack.dwyOuM/check_model.py
python3 /tmp/gd-buttons-ack.dwyOuM/search/run_raw.py --self-test
python3 tools/check-gd-buttons.py
```

The model verifies canonical source/compiler/stock hashes and actual linked
entry/section/symbol/candidate bytes. All **2,304 cases** pass: every decoded
count byte crossed with all valid report counts 0–8, random unrelated high
argument bits, ACK-count wrap boundaries, initial report bytes and preserved
registers. The IRQ-disable mock permits a report-count increment immediately
before masking, requiring the consumer's post-boundary read instead of a
stale snapshot. OID lookup and IRQ controls are explicitly mocked, with
caller-clobbered registers overwritten; no real asynchronous interrupt runs.

Actual stock and candidate instructions have identical combined ordered
data-read/write/call traces. An independent byte-state oracle checks forward
copying, reset/pending states, padding/report preservation and ACK publication
before masking. Checks cover restored r4-r11, SP, return PC and surrounding
memory guards. Bounded stack accesses are allowed but not compared as data
events or presented as identical stack-layout evidence.

Three deliberately wrong variants are rejected by the final checker: a
16-bit decoded count, a pre-IRQ report-count snapshot, and moving ACK count
publication after IRQ masking. This confirms the model catches those specific
width and ordering errors, not every possible semantic defect. It does not
exhaust invalid/corrupted report-count states above eight, establish hardware
interrupt timing, or prove whole-firmware equivalence.

Final canonical `buttons.c` SHA-256:
`e6dcfeb7b77e4bf09facc49cdf8f1ebe563489b66b294e0c02f3bd9da7cdb84b`.
Model SHA-256:
`9d4427cab53793188d2c1d707e49e0f6497a90b5fa1ced84350391f93fbbc8e5`.
Raw-score driver SHA-256:
`de9c7913a81859de34be43da10c05af1123984af96af1b599ad3acc95eb91ba2`.
