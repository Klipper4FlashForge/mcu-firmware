# ADC source-shape recovery

Measured 2026-09-09 with the unchanged shared ATfE configuration. Two more
complete ADC SDK bodies are now exact: `gd_motor_adc_trigger` at ITCM
`0x410..0x43e` (46 bytes), and `gd_motor_adc_special` at `0x748..0x7a4`
(92 bytes). The ADC gate improves from 9/16 exact functions, 688 bytes, to
11/16, 826 bytes. Previously exact ADC functions and every other ADC candidate
section remain byte-identical. These are whole-span results, not normalized
instruction or prefix scores.

## Trigger configuration

The source selects an independent clear mask and shift for each valid group:

| Group | Register-preservation mask | Shift |
|---:|---|---:|
| 1 | `0xcfffffff` | 28 |
| 2 | `0xffcfffff` | 20 |
| Other | return before any MMIO | — |

The original reconstruction selected the complementary field mask and shift,
then negated the mask at use. It emitted 44 bytes with 10/46 positional bytes
matching. Expressing the clear mask directly, but keeping shift-first local
declaration/assignment order, still emits those same bytes. Putting the clear
mask before the shift in both declarations and assignments gives **46/46**.
The compiler selects stock's r3 mask/ip shift allocation and instruction
widths. No register is pinned, and no instruction is supplied by the source.

The actual behavior is unchanged for every 32-bit group and mode: clear the
selected field in control register `adc+8`, then read it again and OR the raw
mode shifted by the selected amount. The two RMWs are not merged. Both shift
amounts are valid for a 32-bit word; mode remains unmasked as in stock.

## Special-function selection: exact and semantically lossless

Enable means exactly 1. All other values clear each requested bit. The three
independent tests select masks `0x100` and `0x400` in `adc+4`, followed by mask
2 in `adc+8`. Multiple requests retain separate volatile RMWs in that order.

Stock computes the first masked value once before splitting the enable and
disable paths. The previous 92-byte C body recomputes branch-specific bit
tests, matching 70/92 bytes. Three hand hypotheses change no emitted bytes:
precompute the first mask; precompute all three masks; reuse the first masked
value in the RMW instead of its immediate constant.

A raw-byte permutation search found an exact candidate by first copying the
32-bit selector into an unsigned 64-bit local used only by these predicates.
After independent semantic review, a simpler equivalent spelling was tested:
the canonical source uses `UINT64_C(...)` for the three predicate masks. This
implicitly promotes the original selector without adding a local. The actual
register update constants and MMIO lvalues stay 32-bit. Its complete body is
**92/92 exact**, independently rebuilt from the full canonical ADC module.

This widening does **not** discard information or change meaning. For every
`f` in `0..2^32-1` and each mask `m` in `{0x100, 0x400, 2}`:

```text
(zero_extend_to_64(f) & m) != 0  iff  (f & m) != 0
```

There is no arithmetic, narrowing, signed overflow or shift involving the
widened value. Enable comparisons, branches, addresses, access widths and
access order remain the same. The public selector/enable ABI and peripheral
storage types are not widened. This is valid matching C, **not evidence that
the original SDK defined 64-bit mask constants**. That source-spelling
uncertainty is retained explicitly rather than interpreting the byte match
as an original type declaration.

Follow-up local-type probes emit 70/92 with `uint32_t`, `int32_t` and
`uint16_t`, versus 92/92 with `uint64_t` and `int64_t`. The canonical form
uses unsigned constant promotion, not a signed conversion or narrowed API.
An independent agent froze and rebuilt the explicit unsigned-wide variant,
confirming all section/symbol/entry checks and the model below. The final
implicit-promotion form was separately rebuilt and checked.

## Search and validation

The four-worker search completes 20,000 iterations in 151.207 seconds:
3,438 compile-error iterations, 16,562 non-error iterations and zero internal
errors. The direct objective checks all 92 bytes plus complete size, section
address, Thumb symbol and ELF entry. Its self-tests score baseline 22,
stock target 0, one-byte growth/truncation 1, displaced section/symbol/entry
3,000,000 and wrong entry 1,000,000. No instruction normalization is used.

Two distinct improving outputs are retained. The nonexact 78/92 candidate
uses the first masked value as a peripheral pointer in its disable branch;
it is rejected by inspection and the guarded execution model. The exact
candidate is simplified as above; its expanded compound assignment and
reversed equality spelling are unnecessary and are not retained.

The bounded stock/candidate model passes 2,304 deterministic cases for both
the search output and final canonical body. It varies all flag combinations,
irrelevant high bits, enable boundary values and random full-word arguments.
Every register read supplies a distinct value to detect cached reads. Ordered
32-bit MMIO reads/writes are compared with stock and an independent mask
oracle; complete modeled peripheral storage, preserved r4-r11, SP, return PC,
execution bounds and stack guards are checked. It is scratch diagnostic
evidence, not a new wrapper gate, hardware test or asynchronous timing proof.
The existing native ADC tests also pass; those cover channel arithmetic,
lengths and resolution, not these two helpers' MMIO timing.

Scratch records are in `/tmp/gd-adc-shapes.oHB137/`. The runner reuses the
reviewed PI raw-score driver with target name/address/size substitutions in
memory; comparison bytes appear only in the target ELF, never candidate C.
Enabled mutation weights match the PI search, including its warning that
temporary creation can change types despite disabled dedicated type mutation.
The random seed stream is not pinned; non-error iterations can be cached.
Some hand-probe source files were edited between trials; their retained ELFs
record those diagnostic measurements, but old source hashes are not claimed
fresh. Canonical reports are regenerated from the final source.

## Other hypotheses not adopted

- Length configuration: independent clear/field masks emit 76 bytes with
  12/70 matching, exceeding the 70-byte stock extent. Reusing a `count-1`
  local for range checks and encoding emits 66 bytes with 13/70 matching,
  but moves the subtraction ahead of the group tests and remains far from
  stock's control flow. Neither replaces the current reconstruction.
- Deinitialization: writing both reset calls separately in each device branch
  produces the same complete 72-byte candidate, still 65/72 matching.
- A global `-fno-jump-tables` diagnostic leaves every ADC body unchanged, but
  the full partial build fails its overlap audit at timer OC shadow versus
  timer-channel enable. It is rejected, not applied selectively.
- `-simplifycfg-hoist-common=true` and `-hoist-common-insts=true` each leave
  every ADC section unchanged in isolated diagnostics. They are not adopted
  or claimed validated against the whole corpus.

Reproduce the durable byte gate with `python3 tools/check-gd-adc-vendor.py`.
Its nonzero overall exit remains expected because five ADC bodies are still
nonexact. The [current plan](../PLAN.md) owns final integration totals.
