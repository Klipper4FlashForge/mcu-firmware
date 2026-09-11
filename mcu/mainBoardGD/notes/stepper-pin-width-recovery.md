# Stepper configuration pin-width correction

Stock `command_config_stepper` occupies ITCM `0x0f08..0x0f72`, 106 bytes.
Its pin arguments are **byte loads** at `0x0f30` (`args[1]`) and `0x0f44`
(`args[2]`). The shared `gpio_out_setup(uint32_t pin, uint32_t value)` API
accepts a full word, so the truncation belongs in this caller. The recovered
calls now pass `(uint8_t)args[1]` and `(uint8_t)args[2]`. No public argument
type, GPIO implementation, compiler flag or data layout changes.

This corrects behavior, not just instruction spelling: an argument such as
`0x100` selects pin zero in stock, while the previous full-word argument
reaches GPIO's invalid-pin path. The invert flag remains a signed-word
positive test; it is not narrowed alongside the pins.

The complete candidate remains **104 bytes**, improving from **29/106 to
31/106 matching bytes**. It is still nonexact. All ten other stepper section
hashes are unchanged, including six exact functions totaling 524 bytes.

## Source-pinned execution check

```sh
python3 tools/check-gd-stepper.py
python3 tools/check-gd-stepper-config-model.py --self-test --out work/mainBoardGD-stepper-config-selftest.json
python3 tools/check-gd-stepper-config-model.py
```

The stepper byte gate still exits nonzero for its existing mismatches. The
model passes **7,210 cases** and **13 self-tests**. Cases cover every low-byte
pin value, high-bit patterns through `0xffffff00`, signed invert boundaries,
raw OID/timing values, both interrupt-mask states, pseudo-pins, invalid ports,
and queue-allocation error paths. There are 6,308 expected shutdown cases.

Both callers execute the **actual stock** GPIO setup/reset/clock, IRQ
save/restore, motor-direction leaf, branch veneer and queue-setup bodies.
The model compares combined ordered argument/state/MMIO/call traces, all
live modeled RAM and register-latch values, call-time stack alignment,
callee-saved r4–r11/d8–d15, returned SP/PC and PRIMASK, plus argument/object/
stack canaries. Only explicitly bounded dead stack temporaries are excluded
from live-RAM equality. Allocation and error lookup/shutdown are explicit
boundary mocks; shutdown is terminal, not a simulated scheduler recovery.

Input source/header/compiler hashes, stock identity, ELF entry/extent and
full candidate/expected byte hashes are checked before and after execution.
Self-tests reject stale or missing provenance, wrong extents/hashes, and each
missing pin truncation. Negative instruction controls are comparison-only
test inputs, never firmware source or candidate linker payloads.

This is a bounded synchronous caller test with MMIO register latches, not
physical GPIO timing or an independent proof of the reconstructed callees.
Executing identified stock dependencies adds no source-recovery coverage.

## Integration isolation

The scratch pre-correction rebuild matches all eleven stepper sections in
the frozen `/tmp/gd-shutdown-loop-final-repeat` baseline. The separate new
partial build at `/tmp/gd-stepper-validation.WLzpFb/partial` changes **only
the nonexact `command_config_stepper` section** among all 543 records.
Every prior exact section is preserved; initialized RAM is unchanged.

Partial parity passes **456/456**, with 87 explicit vector/veneer structural
exclusions and no missing or failed references. Exact C totals remain
**187/281 functions and 11,006 complete-span bytes**; 94 bodies remain
nonexact. The correction adds no exact function and no whole-image claim.

Validation reports are retained in `/tmp/gd-stepper-validation.WLzpFb/`
(`model.json`, `selftest.json`, `parity.json`, and partial `results.json`).
The new config section SHA-256 is
`259f6a80494e2acb5dcdbe0f62797d6dcb7fcc1ef174beffcf02bebd2e00ad79`.
