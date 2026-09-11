# Move-reset source shaping and ordered-memory audit

`move_reset` occupies stock ITCM `0x3ed8..0x3f2e` (86 executable bytes,
no inline pool). The former reconstructed body occupied 88 bytes with
43/86 stock bytes matching; its extra two bytes used the known alignment
gap before `oid_alloc` at `0x3f30`, not another function's body.

The reviewed change spells both `count - 1` expressions with
`INT64_C(1)`. It emits a complete **86-byte body, 66/86 matching**, with
Thumb symbol and ELF entry `0x3ed9`. This is a 23-byte matching gain and
a fitting extent, **not an exact function**. The tail starts at the stock
`0x3f14` again and is identical through its final store at `0x3f2a`;
the return still saves/restores a different register set. The loop's
counter representation and register choices also remain different.
No compiler option, ABI, assembly body or register pinning changes.

## Search and complete saved-output audit

Before the search, explicit-next, countdown and named-loop-end variants
all remained 43/86 with 88-byte extents. Additional local diagnostics
were also rejected: a volatile node store remained 43/86; widening the
loop counter itself produced 41/86 and 100 bytes; a word-sized stride
local produced 22/86 and 88 bytes.

The first search was interrupted after a permuter declaration-list bug;
it is not counted as a completed search. The replacement typed baseline
hoists the loop-index declaration out of `for` syntax and was verified
byte-identical to the canonical 88-byte baseline. The clean run completed
**20,000 iterations in 389.76 seconds**, using one worker, with 5,327
compile-error iterations and zero internal errors: 14,673 non-error
iterations. This count may include cached variants rather than unique
compiled programs.

The search objective compares every byte of the complete 86-byte stock
span at its real entry, penalizes extra/missing bytes, and rejects wrong
section/symbol/ELF entries. Baseline score is 45 (43 differing stock bytes
plus two extra bytes), exact stock scores zero, and size/entry negative
controls remain nonzero. Best score is 20. Enabled mutation families
cover temporary-expression extraction, expansion, statement/declaration
ordering, split/compound assignments, commutative expressions and array
aliases; no compiler flags or ABI declarations are searched. Temporary
extraction can nevertheless create bad types or uninitialized values,
so its outputs are not assumed equivalent.

All 13 saved outputs were independently recompiled with fixed flags and
their complete entry/size/byte scores verified. No output scores below
20, and only `20-1` preserves the required semantics:

| Output | Matching/86 | Size | Audit |
|---|---:|---:|---|
| 20-1 | 66 | 86 | Valid lossless signed-64 constant-one widening |
| 20-2 | 66 | 86 | Reject: self-links and byte-truncated tail index |
| 22-1 | 64 | 86 | Reject: uninitialized loop-index read; changed termination/stride |
| 37-1 | 49 | 84 | Reject: self-links instead of successor links |
| 39-1 | 49 | 88 | Reject: skips first node, self-links, reverses tail publication |
| 40-1 | 46 | 86 | Reject: every iteration writes initial node; repeated stride reads |
| 41-1 | 47 | 88 | Reject: skips first node and writes self-links |
| 42-1 | 44 | 86 | Reject: uninitialized position pointer |
| 42-2 | 44 | 86 | Reject: loop index overwritten with stride |
| 43-1 | 43 | 84 | Reject: old-position self-links |
| 43-2 | 45 | 88 | Reject: free-list publication precedes final-link clear |
| 43-3 | 43 | 84 | Reject: self-links before pointer advance |
| 43-4 | 43 | 84 | Reject: uninitialized pointer stored |

The last-store reordering in `43-2` could leave the same final bytes for
stable, nonaliasing storage, but it does not preserve the stock's ordered
publication and is not adopted.

## Full-domain arithmetic proof

The public/global types stay unchanged: `move_count` is `uint16_t`,
`move_item_size` is `uint8_t`, the loop index is `uint32_t`, and all
pointers remain ARM32 pointers. Count zero returns before either widened
expression is evaluated. Otherwise count is in `1..65535`, so
`count - INT64_C(1)` is exactly `0..65534`. Signed 64-bit comparison
represents every possible `uint32_t` index, and this loop only reaches
indices through 65534. Thus its comparison and number of iterations are
unchanged, without signed overflow or unsigned wraparound.

The final product is at most `65534 * 255 = 16711170`, representable in
the original signed 32-bit arithmetic as well as the widened signed
64-bit arithmetic. The pointer displacement is therefore numerically
identical. No pointer, memory access or store is widened or narrowed.
The same pointer validity/alignment/backing-object requirements as the
original C still apply; widening does not make invalid storage valid.
This establishes equivalence over the full integer input domain where
the original pointer operations have defined behavior. It does **not**
establish that the original firmware author used 64-bit constants.

The initial loop stride/base snapshots and separate final stride/base
reloads remain intact. Stock reads count at `0x3ee2`; when count exceeds
one it reads stride at `0x3efe`, base at `0x3f02`, and writes successive
links. It then reloads stride at `0x3f14`, base at `0x3f1c`, clears the
tail at `0x3f20` and publishes the free list at `0x3f2a`. The candidate
preserves that access sequence, not merely the final linked-list values.

## Independent model and provenance

The scratch checker independently executes stock and candidate against
an ordered-access oracle, with nonaliasing pool, globals and stack:

- All 256 raw strides with counts 0, 1, 2, 3, 7 and 16.
- Additional raw unaligned-pointer cases and count boundaries 255, 256,
  257, 32767, 32768, 65534 and 65535, including maximum stride 255.
- Twenty explicit environment-injection diagnostics immediately before
  the final stride read, changing base/stride/count to verify that only
  the count and loop inputs were snapshotted.
- Complete ordered data reads/writes, complete pool/global byte images,
  callee-saved registers, SP, stack access bounds and surrounding canaries.

The old 88-byte baseline, raw `20-1`, simplified two-`INT64_C(1)` source,
and fresh canonical adopted body each pass **1,656/1,656 cases**. Inputs
and final trace/storage hashes agree. The checker initially refused the
canonical source while its report was stale during adoption, then passed
after a fresh full base gate. That gate reports 40/45 exact functions;
`move_reset` remains unmatched. The simplified source was also freshly
compiled and linked independently, producing the same full 86-byte body.

An intentionally cached-tail negative control is rejected for missing
the final stride/base reads even though its final memory under stable
inputs agrees. Its oversized body is used only in the isolated negative
control, never as a firmware candidate.

These are bounded Unicorn memory-model checks, not hardware/boot tests.
The 862 raw unaligned cases test emitted ARM instructions, not defined
unaligned C behavior. Injected environment changes demonstrate observed
reload boundaries but are **not evidence of real asynchronous writers**
or a claim of thread safety. Stack save layout and caller-clobbered
registers need not equal stock for this void function; preserved ABI
registers and stack bounds must. The pool never aliases globals, and no
pointer wraps outside its mapped storage.

Temporary evidence is retained under `/tmp/gd-base-next.t6Q6vv/` (search,
hand trials and simplified source) and `/tmp/gd-move-reset-model.EJYdNS/`
(model, independent ELFs, all-output audit and results). These scratch
paths are not firmware deliverables. Example rerun:

```sh
python3 /tmp/gd-move-reset-model.EJYdNS/model.py \
  --out /tmp/gd-move-reset-model.EJYdNS/canonical-adopted.json
```

The model checks the current report's source/dependency/compiler hashes,
stock hash, complete section hash and real entry. For scratch candidates,
`--scratch --candidate-source PATH --elf ELF --out JSON` additionally
records the explicit candidate source and ELF hashes. Retained hashes:

- Simplified source: `a86cd276a81d2ff65ca0693c292800cc75b7235d1a973bf4288ec719643fcd47`.
- Candidate 86-byte body: `24725e09fc7abf5ab1a43d71829db12ab2729b9e08e876074eea56d6aa59af05`.
- Stock 86-byte body: `25fd06b476733607d3b6455f325aa481d93142a87f14ec4e38f6a7c93c898405`.
- All-output audit: `30183664d9b300850817c558b99df478b87c24de61225e8bec953c1f5a7db95b`.
- Model source: `6f3bd618af1db9e56d9d60b9e30bd00567503cff8b46a630445faf3edd7a7318`.
- Model inputs: `788a38a12e8226744ecb32ba3dd8a966b4c6a3ad6f793ff0882c1650d3a2532b`.
- Model outputs: `e8d0fd1e4dddb04a9542ee76b46ca474db0d1187d8d871aae1441c7312aa2a71`.

All search workers have exited. The retained C is improved but still
requires further stock-directed recovery; a finite search does not
prove no exact source spelling exists.
