# Motor GPIO-step access-order recovery

`mclib_gpio_step` occupies flash `0x08001670..0x0800170c`, including two
binary32 constants: 156 bytes, followed by four alignment bytes before the
hardware initializer at `0x08001710`. The GPIO layer reaches it through the
ITCM veneer at `0x5ba8`.

The canonical candidate improves from 14/156 matching bytes with a 160-byte
body to **150/156 matching bytes with the correct 156-byte extent**. All other
31 motor section hashes are unchanged, including exact PI and the previously
improved PWM update. The motor gate remains 23/32 exact functions, 1,240 bytes.
This function is not yet byte-exact.

## Observed state publications and reads

Stock reads the timer at `0x4000e024`, then samples the direction byte and
previous step timestamp. It publishes the new timestamp, computes unsigned
wrapping elapsed time, stores the interval at `0x08001684`, and only then reads
the position counter at `0x08001688`. Nonzero raw direction increments the
32-bit position and 16-bit electrical phase; zero decrements them. All widths
and wrap behavior are preserved, with no direction normalization or range guard.

After storing phase at `0x080016aa`, stock explicitly reloads its low halfword
at `0x080016b2`. This snapshot feeds both angle conversion and the quarter-turn
test. The original candidate forwarded the local phase instead of performing
that read. The recovered source now uses a local volatile halfword view for
the snapshot, and local volatile word views to preserve interval publication
before the position read. The direction snapshot remains an ordinary byte
read immediately after the timer sample. No shared header layout changes.

Angle computation remains unsigned-to-float conversion followed by two
separately rounded multiplications: phase times `0x1.921fb8p+1f`, then times
`0x1p-15f`. Combining those constants or changing the operation order is not
part of this recovery.

On a quarter-turn boundary, the stall counter saturates at 255. Only mode 1
transitions to mode 2, clears the idle gate, copies run-current bits into active
current and replaces the interval with the configured idle threshold. Other
raw mode values still record the step without that transition.

## Source hypotheses and bounded search

Scratch records are at `/tmp/gd-step-shapes.KeLdNI`.

| Initial hypothesis | Candidate bytes | Matching bytes |
|---|---:|---:|
| Baseline | 160 | 14/156 |
| Explicit post-store phase reload | 160 | 22/156 |
| Phase reload plus interval publication | 156 | 137/156 |
| Also snapshot position after interval publication | 156 | 136/156 |

The 137-byte-match intermediate seeds a two-worker, 20,000-iteration raw-byte
permutation search. It finishes in 353.18 seconds, with 2,329 compile errors
and zero internal errors. Its minimal source matches the entire independently
compiled full-source intermediate before searching. The scorer checks all
positioned bytes, full section and symbol sizes, actual addresses and the
Thumb/ELF entry; growth, truncation and shifted-entry self-tests cannot score
zero. No alignment normalization or omitted pool is used.

Five distinct outputs are retained and independently rebuilt. Two fail ordered
write checks immediately. The other three pass a 96-case smoke screen but are
inferior to the final candidate. The best raw result is 145/156: its previous
timestamp read moves before the timer sample, unlike stock. It is not adopted.
Another 141/156 spelling has that early-read issue. The 139/156 output supplies
a useful counter-condition hint rather than a wholesale replacement.

That hint introduces an ordinary local `can_count` holding the counter's
availability before the compound source condition. The compiler still emits
the counter load only on the quarter-turn path, but now chooses stock's ITT
sequence instead of a branch. The complete compiled tail confirms there is no
added counter read. Source-level eager evaluation alone is not claimed to
establish access equivalence: the compiled byte and access-model gates do.

Independent stock-directed refinement places a direction snapshot immediately
after the timer read and keeps the position snapshot after interval publication.
Together these produce 148/156 matching bytes; adding the counter hint reaches
150/156. Direction snapshot alone regresses to 164 bytes/32 matches and is
discarded. Making the previous timestamp read volatile, rewriting the counter
as a nested unsigned clamp with a volatile store, or moving the previous local's
declaration earlier gives no further byte improvement and is not retained.

No compiler switches, per-function attributes, register pinning, instruction
blobs or business-logic assembly change. The finite random search does not
prove that no exact C spelling exists; non-error iterations include cached
outputs and the random seed stream is not pinned for replay. The original C
spelling remains unknown. The final six differing bytes only choose different
registers for the timer sample, direction, previous timestamp and associated
initial subtraction/branch; all later instructions and both constants match.

## Bounded follow-up from the 150/156 baseline

A separate follow-up at the 185-exact-function project checkpoint starts from
the current 150/156 candidate, not the earlier 137/156 permutation seed.
Scratch evidence is at `/tmp/gd-step-registers.oMJoB5`.

Three stock-directed type/publication hypotheses test the remaining initial
register lifetimes: widen the direction snapshot from `uint8_t` to `uint32_t`;
hold the previous timestamp in a signed 32-bit local while retaining unsigned
subtraction; and make the existing previous-timestamp store locally volatile.
All three compile to the **same complete 156-byte section**, SHA256
`30c3cbc0389c8349863be135e2215fd573d387e82a08ce76ab0b9da7a201a0d2`.
None is adopted: they add no matching evidence beyond the existing source.

The independently compiled minimal search input matches the full canonical
function byte-for-byte. A fresh two-worker search completes 20,000 iterations
in 360.06 seconds, with 2,546 compile errors and zero internal errors. The
objective directly counts positioned byte differences plus length and actual
section/symbol/Thumb-entry discrepancies. Its baseline is six differing bytes;
exact-target, growth, truncation and shifted-entry self-tests verify the scorer.
Expression temporaries, statement/declaration ordering, assignment splitting,
commutative operands and compound-assignment shapes dominate the configured
mutation weights. Type-randomization, FP-constant/factorization and dummy/no-op
passes are disabled, although temporary generation can itself vary local types
and would still require semantic review of any result.

The best score remains six: **no improving candidate is emitted**, so there is
no candidate to adopt or exempt from behavioral review. This finite search is
negative evidence for these source-shape families under the unchanged common
compiler configuration, not proof that the original C spelling is unavailable.
The random seed stream is not pinned for an identical stochastic replay.

An independent full motor build retains all 32 canonical section hashes and
all 23 exact functions (1,240 bytes). The unchanged step candidate again passes
all 13 provenance/entry rejection self-tests and all 32,256 combined ordered
state/timer-access, integer-oracle, FPSCR and ABI cases. No source, header,
compiler setting or model changes result from this follow-up. The remaining
six differing byte addresses are `0x08001678`, `0x0800167d` (inside the
direction load at `0x0800167a`), `0x0800167e`, `0x08001680`, `0x08001682`
and `0x0800168a`. These encode the initial register choices;
the body from `0x0800168c` onward and both literal constants remain exact.

## Durable behavioral and provenance gate

```sh
python3 tools/check-gd-motor-step-model.py --self-test
python3 tools/check-gd-motor-step-model.py
```

The gate verifies source/header and compiler hashes, pinned stock MD5/SHA256,
the actual ELF entry, Thumb symbol, symbol size, section placement and complete
function/pool bytes. Thirteen negative self-tests reject altered provenance,
candidate bytes, lengths and shifted symbol/section/ELF entries.

The deterministic suite tests 32,256 cases: quarter-turn boundaries and their
neighbors, saturating counters, arbitrary initial state, wrapping arithmetic,
all 256 raw direction and mode bytes, and four rounding modes crossed with
FZ/DN combinations. A separate integer oracle validates every non-angle state
byte, including fields that must remain untouched. Actual stock and candidate
instructions provide the FP comparison; no FP operation or callee is mocked.

The model compares all 792 state bytes, complete final FPSCR, and the combined
ordered trace of state and timer reads/writes, including addresses, widths and
values. It additionally requires two phase halfword reads and exactly one timer
sample. It checks callee-saved r4-r11/d8-d15, SP, return PC, mapped-access bounds
and stack canaries. Literal-pool and stack accesses are bounded but excluded
from the state/timer trace; they are not silently presented as compared events.

This is a synchronous Unicorn model with an ordinary timer-register latch,
not physical FP exception timing, timer timing, asynchronous state mutation or
interrupt validation. Inputs are finite and do not exhaust every possible
state combination. No complete control-loop or firmware equivalence is claimed.
The report and content-based provenance are saved in
`work/mainBoardGD-motor-step-model.json`; combined totals belong to the
[current plan](../PLAN.md), not this isolated evidence.
