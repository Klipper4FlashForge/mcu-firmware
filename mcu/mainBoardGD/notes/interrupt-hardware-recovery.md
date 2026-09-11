# Interrupt, endstop and motor hardware recovery

Stock MD5: `fb64911bac422a27d7ed7fab3597603f`. All offsets below are
execution addresses. ITCM starts at zero and is stored at file offset `0x4418`;
zero is a valid handler address, not an absent vector.

## Interrupt path

| C body | Address | Stock span | Candidate | Exact |
|---|---:|---:|---:|---|
| Motor ADC IRQ, X then extruder | `0x0` | 120 | 120 | yes |
| Motor DMA channel 0 IRQ, Y | `0x80` | 70 | 70 | yes |
| Motor DMA channel 1 IRQ, Z | `0xc8` | 70 | 70 | yes |
| SysTick | `0x140` | 220 | 224 | no |
| ADC flag clear | `0x4d8` | 6 | 6 | yes |
| ADC flag get | `0x4e0` | 150 | 146 | no |
| DMA flag clear | `0x2b28` | 56 | 56 | no |
| DMA flag get | `0x2b60` | 300 | 276 | no |
| Timer task | `0x5868` | 44 | 44 | yes |

The seven two-byte stock fault traps also match. They are intentional
infinite-loop C bodies, not placeholders for missing behavior. The motor
handlers clear the relevant interrupt before calibration, and only call the
control loop when calibration returns zero. X/Y/Z use loop A; extruder uses B.

ADC status selectors are exactly 1, 2, 4, 32, `0x40000000`, `0x80000000`.
Each recognized selector reads status then control even when status is clear;
an unsupported selector returns zero without hardware access. ADC clear
writes the complement directly, without reading status. DMA selectors are
1, 4, 8, 16, 32; hardware channels 0–7 pack into two banks at bit shifts
0/6/16/22. DMA clear deliberately retains the stock SDK read-modify-write.
The current compiler transforms the sparse switches differently from stock.

`python3 tools/check-gd-peripheral-irqs-mmio.py` executes the actual linked
helper sections against stock and an independent mask/address oracle. All
19,090 deterministic cases pass: 66 ADC clear, 2,080 ADC get, 432 DMA clear,
and 16,512 DMA get. Ordered reads/writes, return values and final register
latches agree. No calls are mocked. Full ELF, section, source, stock and checker
hashes are pinned. W0C/W1C side effects, bus timing and concurrent interrupts
are not simulated; this is modeled behavior, not hardware validation.

SysTick fits by consuming the four alignment bytes before USART at `0x220`.
This does not count as byte equality. Plain C conditions remove redundant
loop hints and shrink its previous 228-byte candidate. Explicit continuation
and inlined status-return variants did not restore stock's loop shape.
`timer_repeat_until` is now a real four-byte NOBITS object at `0x24008ab0`.

## Endstop ABI

`endstop.c/.h` recover all five bodies. Configuration at `0xe08` is 50/50
bytes exact; query at `0x13d0` is 144/144, including the local message string
and padding. Home (`0x1360`, 110 bytes), event (`0x2d98`, 146 bytes), and
oversampling (`0x2e30`, 100 bytes) fit but differ.

The OID is 44 bytes, with a 12-byte GPIO handle, next-wake word at offset 32,
trigger-sync pointer at 36 and four byte fields at 40–43. Configuration
explicitly truncates pin/pull protocol words before calling the full-word
GPIO API. Preserve immediate first oversampling, byte-count wraparound,
timer source tag 1 and unchanged flags on completed triggers. No levelBoard
eddy-sensor hooks are transferred. The disabled-home path currently stores
flags/pointer in reverse stock order; this is not a store-order match.

## Motor arithmetic and initialization

Four complete arithmetic bodies cover 474 stock bytes: inverse Park
(`0x08002950`, 26), DQ voltage limit (`0x080015e0`, 144), observer update
(`0x08002c58`, 276), and positive square root (`0x08002df8`, 28). None is
byte-exact. The limiter is 152 bytes and remains explicitly excluded from the
partial link because it overlaps the step handler. The other three fit.

The square-root candidate speculates VSQRT before its positivity test.
For a negative input such as -1, both return zero, but the candidate sets
FPSCR.IOC. This is a known semantic difference, not merely register allocation.
Angle approximation, wrap and velocity-update callees remain unrecovered.

`mclib_hardware.c/.h` recover the full initializer at `0x08001710..0x08001f88`:
2,168 stock bytes, no literal pools, versus a 2,166-byte candidate. All 181
direct call targets and their order agree, independently checked by Capstone.
This does not prove call argument, SDK implementation, timing or boot equality.
Both 6,001-NOP ADC delays, GPIO/PWM/timer/ADC/DMA/IRQ setup and initialized DMA
arrays at `0x24000000`/`0x24000008` are retained.

DMA configuration field +24 is not initialized by stock's caller, although
the SDK reads it to choose control bit 8. The C source leaves it unspecified
and documents it neutrally; it does not invent a zero. Different stack layout
means its value cannot yet be claimed equivalent. No fourth PWM initialization
is invented for the extruder.

## Integration gate

The compiler remains the user-supplied, licence-free ATfE 22.1.0 with the
same global configuration. No per-function flags, fixed registers or stock
opcode arrays are introduced. Caller-specific symbol profiles distinguish a
direct flash call from an ITCM call through a bridge to the same function;
the partial linker accepts differing addresses only when the extracted bridge
map establishes the same destination. Actual C bodies are not patched.

At this checkpoint the partial ELF had 135/195 exact C spans (7,224 bytes), preserving all
121 previous exact functions. There are 60 integrated C mismatches, nine
standalone exclusions, 71 unresolved code targets and two read-only data
dependencies (`encode_acknak` and the parser-error string). The latter are
classified separately from code, correcting the earlier dependency count.
The later ADC/angle/digital-output/runtime pass supplies both objects; see
the [current plan](../PLAN.md) for the newer integration totals.
All initialized RAM,
generated records, vectors, bridges and separately counted architectural
assembly remain exact. These are source-integration checks, not a flashable
firmware or proof of whole-image equality.
