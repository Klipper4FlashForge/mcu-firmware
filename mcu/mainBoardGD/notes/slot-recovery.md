# Fixed-slot source recovery

Measured on 2026-09-09 with the common ATfE 22.1.0 configuration in
[the source README](../recovered/README.md). Full function spans include their
local pools. Fitting a stock slot permits integration; it does not establish
instruction equality, original source identity or firmware bootability.

| Function | Stock start / span | Candidate / positional matching bytes | Result |
|---|---|---|---|
| `mclib_current_acquisition_calibrate` | ITCM `0x3a18`, 68 B | 68 / 68 | exact C |
| `gd_system_reset` | ITCM `0x288`, 36 B | 36 / 36 | exact C |
| `stepper_load_next` | ITCM `0x4850`, 96 B | 96 / 44 | fits, unmatched |
| `gd_motor_timer_oc_shadow` | ITCM `0x4dd8`, 94 B | 94 / 62 | fits, unmatched |
| `gd_motor_timer_slave_mode` | ITCM `0x55a0`, 682 B | 642 / 14 | fits, unmatched |
| `mclib_limit_dq_voltage` | flash `0x080015e0`, 144 B | 128 / 12 | fits, unmatched |
| `gd_motor_irq_enable` | flash `0x08002010`, 102 B | 102 / 100 | fits, unmatched |
| `gd_board_main` | ITCM `0x38b0`, 298 B | 298 / 245 | fits, unmatched |
| `gd_runtime_copy` | flash `0x0800335a`, 14 B | 14 / 14 | exact assembly |
| `gd_runtime_zero` | flash `0x0800336a`, 14 B | 14 / 14 | exact assembly |

## Shared state and native barriers

The calibration routine in `mclib_commands.c` snapshots the 16-bit sample
counter before the first peripheral read, then stores its increment, matching
`0x3a22/0x3a24/0x3a2a`. Both samples are signed low halfwords of four-byte
register slots. At count 2000 or higher, it clears the active flag and commits
the two filtered offsets. Its return is the current flag byte, not a
synthesized boolean. Declaring that shared status byte volatile in
`mclib_state.h` preserves the final reload on inactive and just-completed paths.
The entire `0x3a18..0x3a5c` function now matches, leaving the real following
polarity setter at `0x3a60` unobstructed. State offsets and initialized bytes
remain unchanged. The motor gate records 21/32 exact functions, 1,072 exact
bytes; all 20 other exact functions remain exact.

`core.c` uses `__builtin_arm_dsb(15)` for the two barriers bracketing the AIRCR
read/write at `0xe000ed0c`. The local CMSIS header otherwise selects a GCC-style
inline-assembly spelling under ATfE. The native intrinsic retains both actual
barriers and reproduces the stock constant scheduling in all 36 bytes of reset.
This is a source-level representation of the same architectural operation,
not a per-function compiler option. The core gate is 19/20 exact, 410 bytes;
`command_pa_action` remains unmatched.

`board_main.c` similarly uses native DSB/DMB/ISB intrinsics. Its complete
298-byte span has 245 matching bytes. All 72 MPU/cache MMIO and barrier model
cases pass, but cache hardware effects and bootability are not established by
that bounded execution model.

## Complete bodies that fit without matching

`stepper.c` loads the move's signed addend and next interval, commits its count,
then commits the following interval separately from the wake-time update.
All ordinary state updates precede the GPIO/free calls. This avoids a combined
store and preserves the real out-of-line loader boundary at `0x4850..0x48b0`.
Register allocation and instruction scheduling still differ. The loader model
passes 1,200 cases comparing state, queue effects, return and call ABI. It uses
the real stock queue-empty and queue-pop helpers; GPIO toggle and move-free are
mocked. It therefore does not validate physical GPIO effects, free-list mutation,
overlapping allocations or arbitrary asynchronous interruption.

The timer shadow helper spells out each valid channel's two separate volatile
read/modify/write pairs. Invalid channels perform no access. The full 94-byte
body fits without consuming the next function, but switch-arm layout differs.
The slave-mode helper shares its final shift/write between the empty-route and
existing-route paths. It retains all three unconditional initial reads,
subsequent route reads and clears, and stock's low-eight-bit ARM register-shift
behavior for raw selectors. The empty-route path bypasses later reads. Its
642-byte candidate fits the 682-byte stock span without removing a branch or
inventing input validation. All 7,483 timer ordered-access/configuration/ABI
model cases pass; four timer functions remain byte-exact over 508 bytes.

The DQ limiter in `mclib_math.c` shares the Q=positive-zero store between the
positive and negative D-clamp paths, keeping the circle-limiting arithmetic in
the remaining branch. The candidate retains the non-fused multiply/accumulate,
unordered comparison behavior, square-root call, post-call Q reload and sign
selection. The retained 41,984-case model in
`tools/check-gd-dq-limit-model.py` compares D/Q bits, FPSCR, ABI and motor
canaries over special/random pairs and 16 FPSCR modes. It uses the **stock**
square-root helper. This supports the limiter's source shape, not the separate
reconstructed square root, whose speculative-FP/FPSCR caveat remains open.

For interrupt enable, `(AIRCR & 0x700) - 0x300` is always a multiple of 256.
Testing it against `<= 0x400` accepts exactly the same values as stock's
`< 0x500`, including rejection of unsigned underflow for grouping values 0–2.
This produces 100/102 matching bytes: the endpoint compare and conditional
branch still differ. Priority grouping remains exact, and SYSCFG routing
remains 52/58 matching bytes. All 10,177 DMA/control ordered-MMIO cases pass.
The raw argument ABI and volatile access sequence are retained.

## Assembly provenance is a separate result

`scatter_handlers.S` supplies the copy and zero helpers as symbolic Thumb
assembly because the matching AC6.16 microlib archive identifies `handlers.o`
with `STT_FILE handlers.s`. Its measured archive SHA256 is
`bc6495abee295ddd4f899d104fb82d49e3b0ec48122c9be6283876921547adea`.
That provenance does not extend to the neighboring decompressor and string
helpers: their object metadata identifies C sources. Their unmatched C bodies
must not be replaced with assembly merely to gain an exact score.

Both assembly handlers are 14/14 exact. Copy tests its byte count before the
word load/store loop; zero similarly tests before storing. The 2-byte null handler
at `0x08003368` remains the sole active C definition. The C copy/zero bodies
remain explicitly labeled `semantic_reference`, with no duplicate active
definitions and no contribution to C coverage or the standalone-blocker count.
The assembly model passes 36 ordered-access/output/return cases; the separate
C scatter model passes 86. These are bounded emulation checks, not a board boot.

The independent scatter-data build remains exact over
`0x08003744..0x08004418` (3,284 bytes), using source-built initialized RAM and a
generic source-only compressor. Helper code, load metadata and compressed data
are separate gates; none substitutes for the remaining ITCM payload work.

## Integration and remaining work

The fresh combined link has 175/277 exact C functions (10,024 bytes) and 8/8
exact architectural/runtime assembly spans (236 bytes). All 173 C functions
exact at the preceding integration milestone remain exact. The independent
candidate-parity audit passes 452 sections; 87 synthesized vector/bridge
sections remain explicit structural exclusions from that audit.

Nine source bodies remain standalone-only, and two C handler alternatives are
semantic references. There are six external code targets, one unresolved RAM
binding, nine MMIO bindings and four architectural/layout constants. The
regression records 30/62 passing processes; the remaining failures are the
expected byte mismatches, not a successful whole-image build.

The 45-report inventory has no stale reports or evidence conflicts. Its unique
exact execution-address union is 27,656 bytes, excluding zero-state storage
and accounting for the 144-byte C/data overlap. The 11,912 initialized RAM
bytes are all verified; 49 typed zero-state objects cover 23,675 bytes, leaving
10,301 zero-region bytes unclassified.

[The remaining-code map](remaining-code-map.md) classifies all 2,686 apparent
ITCM/flash gap bytes into verified vectors, bridges, scatter records and
observed zero padding. No nonzero gap is unclassified. That is not a claim
that every source body is exact: the main remaining work is source shaping,
the explicit standalone dependencies, runtime integration and whole-image
layout/compression verification. Zero bytes alone cannot prove original
padding rather than a zero-valued object.

Reproduce the relevant gates from the repository root:

```sh
python3 tools/check-gd-recovery.py
python3 tools/check-gd-stepper-load-model.py
python3 tools/check-gd-dq-limit-model.py
python3 tools/check-gd-timer-vendor.py --self-test
python3 tools/check-gd-dma-control-mmio.py
python3 tools/check-gd-board-mmio.py
python3 tools/check-gd-scatter-handlers.py
python3 tools/check-gd-scatter-runtime-model.py \
  --isolated-report work/mainBoardGD-scatter-handlers/results.json \
  --out work/mainBoardGD-scatter-handlers-model.json
python3 tools/report-gd-gaps.py --out work/mainBoardGD-gaps.json
```
