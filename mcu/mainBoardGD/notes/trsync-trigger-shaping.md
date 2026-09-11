# Trigger command: four-byte scheduling difference

This bounded pass targets `command_trsync_trigger` at ITCM `0x1ee8`,
whose complete stock extent is 152 bytes. Baseline C matches 148/152;
all ten other trigger-sync functions are exact, totaling 752 bytes.
The source and regression gate are `recovered/trsync.c` and
`tools/check-gd-trsync.py`.

## Address-level cause

Only two independent instructions exchange order inside the inlined
callback-dispatch loop setup:

```text
address  stock             candidate
1f22     uxtb r6, r1       movs r7, #0
1f24     movs r7, #0       uxtb r6, r1
```

The rest of the complete body, including loop alignment, calls and
epilogue, matches. This is not an extent, relocation or literal-pool
problem. The byte conversion supplies the callback reason; zero is
used to clear the released signal's two fields. Neither operation depends
on the other, but instruction-order equivalence is not byte equality.

The earlier publication work is documented in
`motor-publication-recovery.md`. This pass preserves its individual
volatile link/callback accesses and does not make additional objects
volatile or alter the shared record layout.

## Three grounded C trials

Each trial was compiled as the complete module under unchanged common
flags and checked over all eleven stock spans:

- Extract `args[1]` into an explicit `uint8_t` local immediately before
  `trsync_do_trigger`, after interrupts are disabled.
- Express the signal-list iteration as a `for` loop with a cursor, still
  reloading `ts->signals` after each callback.
- Express it as a guarded `do/while`, preserving the zero-signal path
  and the callback's ability to change the head.

All three emit exactly the same eleven sections as baseline: 148/152
for the command, ten exact functions over 752 bytes. None is adopted.

## Bounded raw-byte permutation

A minimal typed translation unit retains the original inlined helper
bodies, callback ABI, list publications and external bindings. Its
complete command bytes are checked identical to the canonical baseline
before searching. The search randomizes the command source, not compiler
flags or the helper ABI. The helper definitions remain available to the
compiler; this does not claim to search every possible helper spelling.

The target is the entire 152-byte section, Thumb/ELF entry `0x1ee9`,
with full symbol size checked. The search score is positional byte
differences plus missing/extra-byte and placement/symbol penalties,
without normalization or instruction alignment. Self-tests yield:
baseline 4, exact stock 0, growth/truncation 1, wrong entry 1,000,000,
and shifted section/symbol/entry 3,000,000.

The run caps the seed task stream at 20,000 iterations and uses two
workers, leaving two workers available to the motor agent. Dedicated
type/literal mutation, AST deletion and dummy-arithmetic passes are
disabled. Temporary creation may still narrow a temporary, so any saved
candidate needs semantic review; source mutations are not automatically
safe. No assembly, opcode arrays, register pinning or per-function flags
are permitted.

The run completed **20,000 iterations in 313.48 seconds**, with 2,606
compile-error iterations, zero internal errors and 17,394 non-error
iterations. No improving output was saved; the raw score remained four.
Independent final recompilation confirms 148/152 bytes and the exact
152-byte extent and entry. Source/compiler/dependency hashes remain
fresh. Session 27490 exited cleanly and both workers were released.
No canonical source, compiler flags or scoreboards were changed; all ten
existing exact functions remain untouched.

Scratch sources, complete ELF gates, raw target, fixed compiler/link
inputs, negative tests and run log are retained under
`/tmp/gd-trsync-shape.Vav5VX/`. This is temporary experiment storage,
not a firmware deliverable. Finite randomized trials do not prove that
no matching C spelling exists, and iteration counts may include cached
candidates rather than unique compiled programs.

Canonical source SHA-256:
`269aa870a98f8982eda77544d53b533fb1075456c73156bca6a4bead46622b5c`.
Search summary SHA-256:
`9b608d93dae18cff31baeb500c0cfe0e7630f27e7fa612a191a79b7bbc805883`.
The summary retains complete compiler/source/dependency and local
permuter module hashes as well as self-tests and the final byte audit.

## Adjacent interrupt-control diagnostic

The IRQ-enable near-match is a different issue: stock compares the
masked/subtracted group with `<0x500`, while the retained equivalent
`<=0x400` spelling emits a different immediate and branch condition
(100/102 matching). The group is always a multiple of 256; its unsigned
underflow cases must still take the fallback path. A scratch diagnostic
zero-extends the already-wrapped `uint32_t group` to `uint64_t selected`
and tests `selected < 0x500`. This is lossless, but emits only 25/102
matching bytes with a 98-byte extent. It is rejected. Grouping remains
20/20 exact and SYSCFG routing remains unchanged at 52/58. No global or
canonical source option is changed. The ADC selector's successful local
widening is not a generally transferable fix for SDK range checks.

## Helper-mutated, caller-scored follow-up

A subsequent bounded pass changes which function the permuter mutates:
`settings.toml` selects **`trsync_do_trigger`**, while the linker and raw
scorer still select **`command_trsync_trigger` at `0x1ee8`, 152 bytes**.
Thus this pass searches helper spelling that affects its inlined caller,
not the already-exact standalone helper's own byte score. The complete
minimal baseline is checked identical to the previous command baseline.
Every promising candidate would additionally need all ten previously
exact module functions and the publication semantics to remain intact.

Three new helper hypotheses precede that search, without repeating the
earlier loop variants:

- Keep a losslessly widened `uint32_t` callback-reason local across the
  loop, retaining the public `uint8_t` callback argument.
- Use a losslessly widened `uint32_t` local for the byte-sized flags.
- Name typed null-link and null-callback locals before the loop, retaining
  the separate ordered volatile stores when each signal is released.

All three produce eleven sections identical to the baseline: command
148/152, other ten functions 752/752 exact. No variant is adopted.
The helper-mutated search uses the same fixed flags, full-byte objective,
entry/size negative controls and 20,000-task limit, with two workers.
The old caller-mutated run remains separately retained; its result is not
being relabeled as helper coverage. New scratch records are at
`/tmp/gd-trsync-helper.IHUMyU/`.

This helper-mutated run completed **20,000 iterations in 281.87 seconds**,
with 3,281 compile-error iterations, zero internal errors and 16,719
non-error iterations. No improving output was saved: the full-span raw
score remained four. Independent final recompilation again confirms
148/152 bytes, the complete 152-byte extent and the exact entry. The
source/compiler/dependency freshness checks pass. Session 98761 exited
zero and both workers were released. Canonical source, compiler flags and
scoreboards remain unchanged; no speculative helper rewrite is adopted.

The helper-run summary SHA-256 is
`3ff59d34ee1d070827626916aaa2ca36d9cf5a6fc836daa149271e642bc187df`.
It includes the fixed-input hashes, raw-scorer negative controls and final
audit. This finite randomized search adds helper-spelling coverage but
does not prove that no matching C spelling exists; iterations can include
cached candidates rather than distinct compiled programs.
