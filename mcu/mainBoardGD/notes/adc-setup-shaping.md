# ADC setup one-byte source-shaping investigation

Session: 2026-09-09. No candidate source change is adopted.

`gpio_adc_setup` occupies ITCM `0x2f30..0x300c` (220 bytes, including its
pin table, error string, and padding). The retained compiler configuration
produces the correct entry and full extent with 219 matching bytes. The sole
difference is byte `0x2f3e`: stock `cmp r1,r5` versus candidate `cmp r5,r1`.
The immediately following `beq` uses equality only; later code replaces the
flags before any ordered comparison. This is a code-generation difference,
not evidence for narrowing the pin argument.

The eight-byte structure-return ABI supplies a hidden result pointer in `r0`
and the full unsigned 32-bit pin in `r1`. Stock retains the pin in `r5`, the
result pointer in `r8`, and the table index in `r7`. The table has 21 byte
entries at `0x2fe0`; duplicate zero entries select the first index, 12.
Pin 254 selects channel 18. Values above 255 fail the entire lookup rather
than being narrowed to a byte. The ordinary command caller's byte conversion
does not change the callee's observed full-width ABI.

Prior tests recorded in [compiler/alignment recovery](compiler-alignment-recovery.md) already ruled
out signed/byte index locals (217 matching bytes) and pointer iteration
(unchanged 219). Three additional grounded forms were tested here:

1. Compare losslessly promoted `uint64_t` pin and table byte.
2. Express the bounded scan as a miss-first do/continue loop.
3. Express the scan through an ordinary inlined lookup helper.

Every form produced the same complete 220-byte setup section and every one of
the ten analog-module section hashes matched the refreshed canonical-source
baseline. This includes all six previously exact functions, totaling 498
exact-span bytes. Scratch copies were refreshed with the shared
`sched_shutdown` noreturn/nothrow declaration before these comparisons.

The exact 60-byte `gd_delay_us` at `0x5ae0..0x5b1c` has only one observed
direct caller: setup's `bl` at `0x2f9e`. It initializes DWT only when DEMCR
trace enable is clear, and polls a wrapping 600 MHz deadline with a signed
comparison. Neither this helper nor setup's calibration polling was changed.
No cache object extent is inferred; [ADC cache layout](adc-cache-layout.md) remains the
separate address-cited record of that unresolved RAM layout.

The scratch stock/candidate model explicitly mocks the clock/ADC SDK calls,
delay, GPIO routing, and shutdown lookup. It checks all byte pins plus 42
full-width edge/random values, trace-clock initialized/uninitialized cases,
zero/two unsuccessful calibration polls, combined ordered table/MMIO/call
traces, structure-return contents, r4–r11/SP preservation, and full RAM/stack
guards. All 1,192 cases pass for the unchanged baseline. Source, compiler,
stock, and candidate hashes are verified before execution. This does not
claim an execution model for the lower SDK callees or the delay routine.

Scratch reproduction:

```sh
python3 /tmp/gd-adc-setup.ssXi8q/check.py baseline --out /tmp/gd-adc-setup.ssXi8q/baseline-fresh
python3 /tmp/gd-adc-setup.ssXi8q/check_model.py
python3 /tmp/gd-adc-setup.ssXi8q/search/run_raw.py --self-test
```

The gate's expected nonzero exit reports the four existing nonexact analog
functions; it does not indicate a model failure. The search consumed **20,000 seeded attempts in 676.98 seconds** using one
worker. There were 19,786 scored iterations (including 2,110 compile errors)
and 214 internal failures, which the runner does not include in its scored
iteration count. The internal failures are the permuter's unsupported
`CompoundLiteral` type inference when extracting the structure-return
expression. Thus there are 17,676 non-error scored iterations, potentially
including cached candidates, not 20,000 distinct successfully compiled programs.

The full-span baseline score is one differing byte and remains one. No output
candidate is saved. The process exits zero and its worker is released. Neither
the source nor the mutation configuration changes during the run. This finite
negative result does not prove that no exact source spelling exists.

The raw scorer compares every byte of the complete section and extra/missing
bytes, and requires the observed section address, Thumb symbol, symbol extent
and ELF entry. Its controls score the baseline one, the stock target zero,
growth/truncation nonzero, wrong entry 1,000,000 and shifted placement 3,000,000.
The stock target is comparison input only, never candidate C or candidate
linker input. The minimal search baseline independently reproduces the full
module's 220-byte section before mutation.

Enabled mutations cover expression temporaries/expansion, statement and
declaration ordering, split/compound assignments, commutative expressions
and array aliases. Dedicated type/cast/ABI mutations, dummy arithmetic,
constant mutation, deleted statements and artificial conditional references
are disabled. Temporary extraction can still create semantic changes;
there were no improving outputs to accept or reject. Random seeds are not
pinned for exact stochastic replay.

The exact retained candidate SHA-256 is
`f6ad7ba8caef602c6746a2ab798ef17c6243b161032da2ea679c4251dd9ffaaa`;
the stock full-span SHA-256 is
`3346ba6247af4800af2febd4ed60b76d4de628692f10707bb1fb0599f8f9f3f1`.
Scratch source, linker/compile commands, comparison target, scorer controls,
terminal progress and model remain under `/tmp/gd-adc-setup.ssXi8q/`.
No global setting, calling convention, MMIO access, delay implementation,
cache declaration or scoreboard exact-function count changes from this task.
