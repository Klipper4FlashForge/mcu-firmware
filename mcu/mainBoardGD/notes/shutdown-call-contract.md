# Shutdown's non-throwing call contract

`sched_try_shutdown` now matches the complete 20-byte stock span at ITCM
`0x44d8..0x44ec`. It previously emitted 22 bytes with zero positioned bytes
matching. The unchanged global ATfE configuration is used throughout.

The missing declaration detail is `nothrow` on the already `noreturn`
`sched_shutdown` callee. This is a semantic property of the actual routine,
not a per-function optimization option: stock disables interrupts, then
restores its saved integer context through `longjmp`. Neither the IRQ
primitive nor that architectural context restoration invokes a language
exception unwinder. A nonlocal jump does not constitute throwing an exception.
Independent review checked these instructions and the same distinction in
the locally available standard `longjmp` declaration.

Without the non-throwing contract, the compiler conservatively saves LR on
entry to the conditional caller, even though its call branch never returns
normally. With the correct contract, the normal path tests the status byte
and returns directly; the shutdown path uses the stock frameless `BL`.
The proof concerns actual behavior and compatible matching C, not the
original compiler release or original author's attribute spelling.

The annotation is applied consistently to all 13 caller declarations and
the definition, including the protocol unit's existing wider declaration.
No argument types, public calling conventions, compiler flags, linker
scripts or instruction bodies are altered. The prior argument declarations
are not silently unified or narrowed as part of this change.

A complete scratch integration compares all 543 sections against the frozen
186-function checkpoint. **Only `sched_try_shutdown` changes**. All 186 prior
exact C functions and every other exact section remain byte-identical.
The scratch result has 187/281 exact C functions and 11,006 exact-span bytes;
the fresh canonical base gate has 41/45 exact functions and 2,548 bytes.
Whole-image equality is still unverified. Final combined totals belong to
the [current plan](../PLAN.md).

## Actual nonlocal-jump execution check

The scratch checker runs the actual stock and candidate try-shutdown bodies
with actual stock shutdown, IRQ-disable, bridge and architectural `longjmp`
instructions. No callee is mocked. Those dependency bodies have separate
exact compiled gates; this execution check does not relabel stock dependencies
as new C coverage.

All **3,614 cases** pass: all 256 status bytes crossed with six boundary
reason bytes and both initial IRQ-mask states, every reason byte on the
shutdown path, and 30 additional raw upper-word argument diagnostics.
The latter are emitted-ARM tests outside the byte-argument C ABI, not a reason
to widen the public type.

Checks include the ordered memory/call trace, complete guarded context and
stack bytes, preserved/restored integer registers, SP, PRIMASK, return/jump
destination, unchanged shutdown-state byte, and the observed `longjmp(0)`
conversion to one. Context values are prescribed. This is not an asynchronous
interrupt, language-exception, physical exception-timing, scheduler or boot
test. Source/compiler/stock/ELF/checker hashes are retained with the result.

Scratch evidence is in `/tmp/gd-scheduler-next.HDNHDGRx/`: `all-nothrow/`
contains the broad integration; `check_shutdown.py` and `shutdown-model.json`
contain the execution check. Rerun after a fresh canonical base gate:

```sh
python3 tools/check-gd-base.py
python3 /tmp/gd-scheduler-next.HDNHDGRx/check_shutdown.py
```

The complete matched function SHA-256 is
`636c2645f7fccb423da95769ee07ecd763f06825e388d7f9adb2a7bb8e9ae3e5`.

## Rejected surrounding hypotheses

An explicit early return and a while spelling of try-shutdown produce the
same old 22-byte body. Neither is adopted. Task-busy's signed comparison
remains 5/24 matching bytes in an 18-byte body: spelling `> -1`, using a
signed-64 comparison constant, a local volatile byte view, and an explicit
signed-word local all compile byte-identically. Stock uses a signed-byte
load and `CMP #-1`/`IT GT`; the compiler's current equivalent sign-bit test
does not reproduce it. No widened global or per-function code-generation
option is introduced. These hand trials are not a claim of exhaustive
source-search coverage.
