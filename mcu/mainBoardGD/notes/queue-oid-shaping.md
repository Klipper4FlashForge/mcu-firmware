# Queue setup and OID iterator: bounded source searches

Both functions retain their existing complete candidate bodies under the
shared ATfE configuration. No speculative source change is adopted here.
The separate consistent shutdown declaration correction is recorded in
[shutdown call contract](shutdown-call-contract.md); it leaves these bytes
unchanged.

## Queue setup

`move_queue_setup` is 82/84 bytes exact at ITCM `0x3e80..0x3ed4`, including
the local invalid-size string and padding. Only the signed compare operands
and complementary IT condition differ at `0x3ea4/0x3ea6`: stock compares the
old byte stride against the signed request and stores under LT; the candidate
compares the request against the old stride and stores under GT.

The full signed `int` request domain must survive. Negative sizes are not
silently reclassified as huge unsigned values; they do not update the byte
stride. Requests above 255 or an already allocated move pool take the
observed shutdown path after clearing both queue pointers.

| Hand hypothesis | Candidate bytes | Matching/84 |
|---|---:|---:|
| Reverse comparison operands in source | 84 | 82 |
| Named signed-word snapshot of byte stride | 84 | 82 |
| Losslessly widen stride to signed 64-bit for comparison | 92 | 36 |
| Losslessly widen request to signed 64-bit | 92 | 36 |
| Return early on the complementary comparison | 84 | 82 |
| Negate the complementary comparison | 84 | 82 |

The oversized wide-comparison forms are rejected. The other four emit
exactly the existing section and provide no byte improvement.

## OID iteration

`oid_next` occupies ITCM `0x4020..0x405a`, 58 bytes, and matches 53/58.
Stock retains the byte count in LR and the table pointer in IP. The
candidate reverses those two register assignments. It already preserves
the count/table snapshots, byte-wrap iteration and table lifetime across
the index-byte publication.

Three hand hypotheses leave all 58 candidate bytes unchanged:

- Zero-extend the count into a `uint32_t` local.
- Use a `uint32_t` index local while explicitly retaining byte wrap on
  every increment.
- Zero-extend the count into an `int32_t` local.

The stored index remains a byte, table entries remain eight bytes, and no
new table/global reload is introduced. No ABI or global type is changed.

## Completed searches

Each search starts from minimal typed C independently verified identical
to its complete canonical body. The raw objective includes every positioned
byte, any extra/missing bytes, section address, actual Thumb symbol, symbol
size and ELF entry. Exact comparison targets score zero; growth/truncation
and wrong entries score nonzero. Comparison-only stock target sections never
become candidate source or linker input.

| Target | Iterations | Compile errors | Internal errors | Seconds | Best raw score |
|---|---:|---:|---:|---:|---:|
| Queue setup | 20,000 | 1,597 | 0 | 472.04 | 2, unchanged |
| OID iterator | 20,000 | 3,268 | 0 | 474.47 | 5, unchanged |

Each run uses one worker and finishes normally. Neither saves an improving
candidate. Non-error iterations may include cached candidates; these are not
counts of distinct programs. The random seed stream is not pinned for exact
stochastic replay. This finite negative result does not prove that no exact
source spelling exists.

Mutation families cover temporaries/expression expansion, statement and
declaration ordering, split/compound assignments, commutative expressions
and array aliases. Dedicated type/random-constant, deletion, dummy arithmetic
and artificial conditional-reference mutations are disabled. Temporary
creation can still change types or semantics, so any output would require
independent review rather than being accepted for its score alone.

Scratch sources, commands, target construction, raw-scorer controls and
terminal progress records are retained under
`/tmp/gd-scheduler-next.HDNHDGRx/queue_search/` and `oid_search/`.
Both original process handles exited zero and their workers were released.
Canonical full-section hashes remain:

- Queue setup: `1068840410038f86db8ffd79b1b5af5260e5bee98dd3fd4f7bc8fb27ea289dc9`.
- OID iterator: `d9e5921b1b2fc46c5c26b31ef7513b301aa2b715a63d03c8d08ec7575804e833`.

These two unresolved bodies remain explicit in the base gate. Queue push,
move reset, statistics and try-shutdown have separate recovery records;
their results are not added to these search scores.
