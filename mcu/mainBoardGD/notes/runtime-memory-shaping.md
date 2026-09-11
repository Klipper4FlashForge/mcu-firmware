# AEABI memory-move source-shape investigation

This bounded pass targets the C-origin shared copy/move body at flash
`0x080003f4..0x08000434`, exactly 64 bytes with no inline pool. The retained
C emits 78 bytes at the correct Thumb entry `0x080003f5`, with 3/64
positioned bytes matching. It remains a standalone exclusion; none of
the extra 14 bytes may overlap the following set helper in a firmware
link. Both AEABI copy/move names share this void-return body, not standard
C `memmove`'s returned-destination ABI.

The existing [runtime provenance](runtime-compiler-provenance.md) and
[call-boundary experiment](runtime-call-boundary.md) were reviewed first.
This pass does not repeat size/CPU options or set/clear grouping trials.
It uses the unchanged common ATfE flags, not per-function settings,
register pinning, assembly substitution or linked stock library code.

## Stock-directed hand trials

Stock selects backward copying by the unsigned address difference at
`0x080003f6..3fa`. That path forms end pointers, then uses a bottom-tested
decrement/borrow loop. Forward copying checks both pointer alignments
before its word loop; the word transfers at `0x0800041a/41e` use compact
LDM/STM, then the byte tail uses another bottom-tested decrement loop.

The current compiler rotates these loops. It indexes backward bytes,
uses wide post-increment word transfers, and introduces separate
forward-tail setup. The three new hand hypotheses produce:

| Hypothesis | Complete size | Matching/64 | Result |
|---|---:|---:|---|
| Explicit stock-shaped labels/test blocks and exits | 78 | 3 | Entire body identical to baseline |
| Typed word cursors with post-increment transfers | 86 | 2 | Worse: extra pointer rebasing/alignment code |
| Explicit unsigned decrement-sentinel tests | 78 | 3 | Entire body identical to baseline |

The decrement-sentinel spelling compares the decremented `size_t` with
`SIZE_MAX`; it is equivalent to testing the old value against zero over
the full unsigned count domain. No signed count restriction is assumed.
The typed-word trial retains `__may_alias__` and only enters on aligned
pointers, but does not select stock's compact word instructions.

## Search constraints and model

A subsequent one-worker search uses a minimal baseline proven identical
to the full 78-byte candidate. Its objective compares the entire 64-byte
stock span, penalizes extra/missing bytes and validates section, symbol
and ELF entry. Baseline score is 75 (61 differing stock bytes plus 14
extra bytes); stock scores zero. Growth/truncation and shifted/wrong
entry controls remain nonzero.

Enabled families cover expression extraction/expansion, statement and
declaration ordering, split/compound assignments, commutative expressions
and array aliases. Explicit type/cast/ABI mutation families are disabled.
The scratch runner additionally sets the local permuter's hidden
temporary-type randomization probability to zero, without editing the
tool repository or compiler flags. Nevertheless, reordering expressions
with side effects can change meaning, and all outputs require review.

The serializer silently omits the original typedef's `__may_alias__`
attribute. That is a tool limitation, not a license to remove the
canonical alias contract. Every retained candidate is independently
recompiled both as emitted and after mechanical restoration of the
required attribute. Behavioral checks use the restored version. The
search result is therefore qualified by this serialization limitation;
an unqualified emitted source is never an adoption candidate.

A scratch Unicorn model executes stock and candidate instructions
independently against an ordered-access oracle. It checks forward and
backward overlaps, equal pointers, disjoint buffers, all four source and
destination alignment classes, zero counts, word/byte boundaries and
counts through 1,024. It requires exact ordered reads and writes with
their widths and values, complete backing-buffer bytes, preserved
callee-saved registers/SP, bounded stack accesses and canaries. Forward
word copying is allowed only when both pointers are aligned; no
speculative overread or byte-for-word substitution can pass the trace.
The void ABI does not require caller-clobbered registers or flags to
equal stock.

Stock and the unmodified baseline pass all **2,768 cases**. This is a
bounded ordinary-memory model, not physical hardware, whole-firmware or
unbounded-buffer validation. Full integer/alias semantics still require
source review. No real library code is inserted into a candidate body.

Temporary evidence is in `/tmp/gd-memmove-shape.2iXc0Z/`: hand sources and
fixed-flag gates, `search/`, the ordered-memory checker, complete saved
output audit and terminal summary. These paths are scratch evidence,
not firmware deliverables. Canonical C remains unchanged.

## Completed result

The search completed **20,000 iterations in 447.21 seconds**, with 4,534
compile-error iterations, zero internal errors and 15,466 non-error
iterations. It saved 535 distinct emitted-byte improvements below the
raw baseline score. The final independent audit recompiles all of them,
validates their complete entry/extent/byte scores and restores the alias
qualifier. Restoring that qualifier changes **zero of the 535 bodies**.
This measures the retained outputs; it does not claim that the serializer
preserves source semantics in general.

Of these outputs, 533 fail the ordered-memory smoke checks. All 120
candidates that fit at most 64 bytes are among the failures. The best raw
score, 53, belongs to `output-53-1`: it has a 64-byte body with only 11/64
matching stock bytes. It moves the forward byte transfer outside its
loop, causing an unconditional read/write even when count is zero. This
is a concrete semantic failure, not a candidate to truncate or integrate.

The two smoke-test survivors, `output-74-1` and `output-74-4`, merely
reverse the initial local pointer declarations; the latter also reverses
the equivalent operands of the overlap comparison. Each remains 78
bytes, with 4/64 matching. Their fully alias-qualified bodies pass all
2,768 ordered-memory cases, as does a clean full-source declaration-order
variant. All produce the same trace/storage result hash as stock. The
trivial one-byte gain does not fix a loop or extent and is **not adopted**.

The final audit pins the unchanged canonical source/dependency/compiler
hashes, stock hash, fixed invocation and source/ELF hashes. Full model
input SHA-256:
`ede1646f4981e983e46214efb7d210ed5bd68f47e7e78ab6fcd09d926a8610f2`.
Ordered output SHA-256:
`2fa1f4d8b447508ed3dfba10ba5b668fbb5c9f6b988f06ab5d969b5229c3cdf6`.
Terminal summary SHA-256:
`74c3e17fd99aad1568fc49b3fc25d4f3892556874137597a1630d92f46363dcd`.
Complete saved-output audit SHA-256:
`98a7abba696bb03b76ee6502c8a7ea2ff3bea6508255a919ba3183a180d2f680`.

Session 79045 exited zero and its worker was released; the final audit
session also exited zero. All canonical C, compiler flags and scoreboards
are unchanged. This closes these three hand shapes and this bounded
source search, not the possibility of a future exact C reconstruction.
Iteration counts can include cached candidates, and finite random trials
are not an exhaustive source-space proof.
