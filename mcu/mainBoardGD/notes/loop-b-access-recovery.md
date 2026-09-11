# Loop B ordered-access and eager-FP recovery

The complete Z/extruder control-loop body at flash `0x08001258` now has the
correct **860-byte extent**, including its final 44-byte literal pool at
`0x08001588..0x080015b4`. It matches 104/860 positioned stock bytes, up from
68/860 with an 852-byte candidate. It remains **nonexact**: register allocation,
instruction scheduling and branch shapes still differ. The eleven literal
words occupy their stock positions and match exactly.

Only `mclib_control_loop_b` changes in the complete motor gate; the other 31
section hashes are unchanged, preserving all 23 exact motor functions and
1,240 exact bytes. No shared header layout, compiler flag, per-function
attribute, register pinning or business-logic assembly changes.

## Stock evidence and corrected behavior

Stock observes more than the final field values. The prior C candidate
forwarded values and combined publications that stock performs separately.
The revised function uses explicit snapshots and a function-local volatile
view for the observed state transactions. The shared structure itself remains
unchanged. This is evidence-backed target recovery, not a claim that the
original source used these exact qualifiers or names.

| Stock locations | Restored observation/publication |
|---|---|
| `0x1272..0x1282` | Previous timestamp and interval reads, sampled-time word publication, stall-limit read, elapsed-time word publication, in that order. |
| `0x1294`, `0x129a` | Timing-gate byte publication precedes clearing the stall counter. |
| `0x12ca..0x12e4` | Angle snapshots and **both** directional subtractions before selection. |
| `0x12f0`, `0x1306`, `0x1324` | Initial phase-error publication and conditional wrap publications. |
| `0x130a`, `0x1356` | Phase-error reload between wrap checks and again for filtering. |
| `0x1328..0x1372` | Current/EMF/filter snapshots followed by separately ordered filtered-projection, absolute-projection and filtered-phase publications. |
| `0x1382..0x13b0` | Raw-stall publication, conditional gate/counter reads, raw-stall reload at `0x13a0`, output publication and mode read. |
| `0x1452` | Fresh mode read after interpolation; the earlier candidate carried the mode through that block. |
| `0x145a..0x1484` | Idle threshold, delay, elapsed and hold-current snapshots; decrement publication before conditional hold clamp. |
| `0x148a` | Electrical-angle reload before the sine/cosine call. |
| `0x14ae..0x14b2` | Zero d-target publication before active-current read and q-target publication, not a combined doubleword store. |
| `0x152a`, `0x153e`, `0x1552`, `0x1556` | Alpha/beta voltage reloads between clamp stages and before PWM scaling. Each voltage is read three times. |

Addresses in this table are flash offsets with the common `0x08000000` base.
The model checks the complete combined read/write/call trace, not just these
selected examples or a sorted read multiset.

### An unused subtraction changes FPSCR

Stock computes `observed_angle - commanded_angle` at `0x080012d6`, then
`commanded_angle - observed_angle` at `0x080012da`, and selects by direction
at `0x080012e4`. The original reconstructed ternary emitted only the selected
subtraction. That loses observable floating-point work.

A concrete counterexample uses nonzero direction, commanded angle `-1.0f`,
observed angle `0x7f7fffff` (maximum finite binary32), and rounding toward
positive infinity. The selected negative result remains finite. The unused
positive subtraction overflows, so stock sets FPSCR's overflow-cumulative bit
`0x4`; a candidate that omits that subtraction does not. Identical final motor
fields are insufficient to establish equivalence here.

The recovered C therefore evaluates two named subtraction results before
selection. No negation shortcut, reassociation or fused replacement is used.
A compiled negative-source control replaces the reverse subtraction with the
negation of the forward expression. The checker requires unchanged final
motor/acquisition/PWM state **and** detects its missing overflow flag.

Other FP constraints remain explicit: phase wraps are conditional publications,
the projection/filter products retain non-fused rounding, and lower clamps use
the stock unordered-inclusive condition. Independent operation scheduling is
still nonexact; physical exception timing is not claimed.

## Bounded source experiments

Scratch records are at `/tmp/gd-loopb-access.W4LnUc`.

| Probe | Candidate bytes | Matching bytes |
|---|---:|---:|
| Previous canonical body | 852 | 68/860 |
| Mode reload only | 840 | 64/860 |
| Phase-error publications/reloads only | 864 | 63/860 |
| Voltage clamp/scaling reloads only | 852 | 69/860 |
| Combined reloads plus raw-stall reload | 852 | 76/860 |
| Also evaluate both directional subtractions | 844 | 105/860 |
| Complete observed state-access order, adopted | 860 | 104/860 |

The mode-only probe removes one saved register, demonstrating that the missing
reload was also extending a source value's lifetime. The combined intermediate
still fails eight of 5,120 FPSCR comparisons because it omits the unused
subtraction. Adding both subtractions fixes those FP comparisons, but all
3,840 active-mode cases still differ in the combined access trace. Those
failures are corrected, not waived. The adopted full ordered body then passes
the expanded suite. No permutation search is launched in this batch.

## Durable component model and its limits

```sh
python3 tools/check-gd-loop-b-model.py --self-test
python3 tools/check-gd-loop-b-model.py
```

The suite runs **37,888 cases**: 2,368 deterministic input vectors crossed with
four rounding modes and FZ/DN combinations. It includes raw mode/direction
bytes, stall counts around 16/17 and 255, timing equality and adjacent values,
signed elapsed boundaries, zero/one intervals, finite extremes, signed zero,
subnormals, infinities and NaNs. Zero intervals and invalid/out-of-range
float-to-int conversions test actual target VDIV/VCVT behavior; they do not
turn undefined or implementation-dependent C edge cases into portable promises.

Every comparison covers all 792 motor bytes, 48 acquisition bytes and 12 PWM
bytes; combined ordered state/timer accesses and call arguments; complete
FPSCR at each call and final return; saved r4-r11/d8-d15; returned SP/PC; aligned
SP at calls; mapped-access bounds and all three objects' neighboring canaries.
Stack canaries are checked. Literal-pool and stack data accesses are guarded
but excluded from the combined state/timer trace.

All **11 external call sites are explicit mocks**: acquisition, observer,
trigonometry, Park/inverse-Park, PI, voltage limiting and PWM interfaces.
They validate argument/pointer contracts, supply deterministic outputs and
clobber caller-saved core/FP registers and APSR NZCV. They preserve FPSCR so
caller exception evidence remains visible. This validates the caller against
stock under those contracts; it is not an independent full motor oracle,
callee-equivalence proof or hardware simulation.

Two emulator details are controlled explicitly:

- A real stock VLDR primes Unicorn's lazy FP context before test state is
  installed. Requested FPSCR is checked before and at entry and at the first
  pre-arithmetic call boundaries. Fresh-instance tests cover all 16 settings,
  preventing an initial mode-zero run from hiding reset-to-default behavior.
- Calls are mocked at decoded caller BL boundaries. Sequential Thumb decoding
  stops before the ELF `$d` literal mapping and rejects any intercepted BL
  inside an IT block. Only then does the model clear stale emulator ITSTATE at
  the architectural call/return boundary; a deliberately conditional-call
  decoder control must fail. This workaround does not validate real interrupt
  or exception timing.

The checker validates current source/header and compiler hashes, pinned stock
image identity, actual ELF/Thumb entry, full function symbol/section extent,
literal-pool mapping and complete expected/candidate byte hashes. The 19
self-test controls cover provenance, entry/extent/pool corruption, conditional calls,
fresh FP initialization and the missing eager subtraction.

Canonical reports, including the canonical checker's SHA256 and content-based
provenance, are `work/mainBoardGD-loop-b-model.json` and
`work/mainBoardGD-loop-b-model-selftest.json`. This is a finite synchronous
component comparison, not exhaustive input coverage, asynchronous mutation,
physical FP timing or whole-firmware equivalence.

Recorded canonical artifact SHA256 values:

- Checker: `b85d3124f8c0851cdfcfda73c73ab49dca177bb2a59b56f044d4f4670dbcecb5`.
- Stock 860-byte span: `b18545139a92e71ec5afa517a9f886d4c1ca9aaf7f0c3b5477d107a565361877`.
- Candidate 860-byte span: `6656ce68aab88d6d7b9c827bb283fbd72f67d9a77dcaa34cebb42087795fc972`.
