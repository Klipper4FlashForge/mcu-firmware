# ADC, digital-output, angle and scatter-runtime continuation

Stock MD5 `fb64911bac422a27d7ed7fab3597603f`; the same global ATfE 22.1.0
configuration is used for every C body. ITCM addresses below are execution
addresses, with file offset `+0x4418`. Flash starts at `0x08000000`.

## ADC SDK

`adc_vendor.c` implements 16 complete functions, totaling 1,072 stock bytes.
Nine functions are exact, 688 bytes: calibration, calibration count, DMA
enable, DMA repeat, ADC enable, inserted-channel setup, interrupt enable,
regular-channel setup, and resolution.

The two channel setters are 140 bytes at ITCM `0x440` and 402 bytes at
`0x578`, with complete bodies exact. The inserted rank wraps to eight bits
after adjustment by the configured sequence length. The regular rank remains
full-width. Preserve the endpoint cases' ADD rather than OR: unmasked channel
arguments can carry into adjacent fields. Other rank cases clear and OR.
Branch-local volatile reads and that arithmetic distinction reproduce the
stock bytes without compiler-setting changes.

Other preserved details include two separate clear/reload/OR register
transactions, validation before access where stock does so, ADC2's special
resolution encoding, unknown-address clock fallback to `0x40012704`, and
calibration polling with its real NOP and no invented timeout. Deinit occupies
72 bytes at `0x390`, not the decompiler's cross-function 102-byte span.

`check-gd-adc-vendor.py --self-test` compiles the actual four relevant C bodies
natively and tests 520 ranks, 17 extreme parameter values, both channel groups,
length limits, resolution and invalid selectors. Its independent expected
register calculation passes. This is not ARM instruction, volatile bus-order,
polling-time or hardware validation; the nine exact byte gates are separate.

## Queued digital output

`digital_out.c/.h` recover nine complete bodies. Three match exactly:
queue implementation `0x1ac0` (146 bytes), direct set `0x1ce0` (18), and
PWM-cycle set `0x1cf8` (116). The remaining six fit but differ.

MainBoardGD's command entry `0x1a88` is not the upstream queue implementation:
it clamps the requested clock to at least current time plus 5,000 microseconds,
then calls the out-of-line queue function. Timer source tags are 15 for queue
insertion and 14 for immediate updates. The OID is 56 bytes, including the
12-byte GPIO handle at offset 24 and move queue at 44; each move is 12 bytes.

Shutdown passes the default-on mask value 16 into GPIO, not boolean 1. This
matters to the full-word motor-direction handoff. Raw-value boolean predicates
keep load/update candidates within their slots without changing behavior.
An agent's one-off ARM smoke comparison passed 3,387 cases, using modeled
external GPIO/queue/timer effects. That smoke harness is not a retained
regression tool; it is supporting evidence, not a reproducible hardware claim.

## Angle functions and numeric table

`mclib_angles.c` recovers wrap at flash `0x08000848` (72 stock bytes),
atan approximation at `0x08000890` (640), and observer velocity update at
`0x08002d70` (136). All fit, but none is exact: candidates are 60, 640 and
132 bytes. Atan matches 599 of 640 positional bytes; comparison operand
ordering and one octant's constant/register scheduling still differ.

This approximation is not interchangeable with libm atan2: X equal to zero
returns positive zero for every Y. Only three octants clamp the unsigned
interpretation of the converted index to 100. Fraction calculation uses
independent VRINTZ rounding; quadrant offsets have different binary32 pi
roundings and operation placement. Wrap retains stock's NaN/infinity
nontermination. Numeric/FPSCR equivalence is not claimed for unmatched bodies.

The table at `0x0800338c..0x08003524` contains **102**, not 101, binary32
samples. Index-100 branches load the next sample, establishing the final entry.
The table ends exactly at the existing APB shift table. Typed hexadecimal
float constants reproduce all 408 bytes; recomputing atan samples from a
host math library would not necessarily preserve the stock rounding.

## Scatter runtime and protocol data

`runtime_scatter.c` provides complete C decompressor, word-copy, no-op and
zero-fill bodies. Their stock extents are 94 bytes at `0x080004ec`, 14 at
`0x0800335a`, 2 at `0x08003368`, and 14 at `0x0800336a`. The extra BX LR at
`0x08003368` is its own retained no-op entry, not part of the copy loop.
Only the no-op is exact. The other candidates require eight-byte input
alignment and are oversized; all three remain explicit standalone exclusions.

`check-gd-scatter-runtime-model.py` executes stock and candidate helpers with
no mocked calls. All 86 cases agree in source/output access order, final bytes
and the decompressor's zero return; callee-saved integer registers and stack
canaries are checked too. Tests include the actual 11,912-byte RAM
expansion, 28,120-byte ITCM copy to address zero, 33,976-byte zero region,
distance-encoding boundaries, zero word counts and zero requested decompressed
size. Stock still processes one token for the latter, and can emit a literal.
Shifted candidates execute at their actual isolated ELF entries; this does
not conceal their final-link failure or establish a bootable runtime. Invalid
streams and non-word copy/zero counts remain outside the runtime contract.

`protocol_data.c` adds the eight-byte parameterless ACK encoder at `0x68e8`
and the 21-byte parser-error string at `0x6dc2`, both exact. The string is the
separate tail copy, not the identical text in the lookup's local pool.
These two objects resolve the previously explicit read-only dependencies.
The generic gate now verifies actual STT_OBJECT, non-executable read-only
sections separately from function spans, including imported-profile hashes.

## Integration result

All previous 135 exact C functions remain exact. The partial link now checks
224 C bodies, of which 148 are exact, 8,194 complete-span bytes. Another 437
bytes are separately verified numeric/protocol constants. Architectural
assembly remains 178 bytes, and initialized RAM, symbolic vectors/bridges,
retained declarations and scatter load data remain exact.

The retained `check-gd-partial-parity.py` checks partial sections against their
canonical isolated candidates, including all unmatched C bodies. Persistent
ELFs are re-read; temporary startup/generated ELFs are represented explicitly
by fresh full-span report digests. Vector and bridge synthesis is separately
classified and does not count as an independent isolated comparison.

Seventy-six integrated C mismatches, twelve standalone exclusions and 46
unrecovered code targets remain. No currently referenced read-only data or RAM
symbol remains external. The deduplicated runtime-address exact union is
25,139 bytes, including the independently checked eight-byte APB table but
excluding separately measured zero storage, vectors/bridges and
the independently checked scatter-load artifact. This is not a percentage of
the compressed stock image and not whole-image equality.
