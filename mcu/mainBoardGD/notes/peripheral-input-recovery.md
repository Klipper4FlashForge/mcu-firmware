# Peripheral initialization, inputs and trigonometry

Session: 2026-09-09. These are complete reconstructed C bodies and typed
constant data, compiled with the retained common ATfE configuration. They are
not a complete firmware image or permission to flash the partial ELF.
Stock disassembly in `work/itcm.lss` and `work/flash.lss` determines instruction
boundaries, register transactions and ABI; Ghidra is navigation evidence only.

## Measurements

Full function spans include embedded switch tables and literal pools, but not
unrelated trailing alignment. An exact-span total counts only entire matching
functions, not positional matching bytes from an unmatched function.

| Source | Complete bodies | Exact bodies | Exact-span bytes / stock spans |
|---|---:|---:|---:|
| `recovered/timer_vendor.c` | 11 | 4 | 508 / 3,286 |
| `recovered/dma_vendor.c` | 6 | 2 | 36 / 446 |
| `recovered/interrupt_control.c` | 3 | 1 | 20 / 180 |
| `recovered/analog_in.c` | 10 | 6 | 498 / 1,036 |
| `recovered/buttons.c` | 6 | 3 | 368 / 782 |
| `recovered/mclib_trig.c` | 2 | 0 | 0 / 728 |

This adds 38 complete C bodies and 16 exact functions, totaling 1,430 exact
function-span bytes. Three of the new candidates exceed their fixed slots and
remain standalone: timer OC shadow, timer slave mode, and motor sine/cosine.
Their source is retained; no instructions are truncated or replaced by stock
bytes to make the integrated link fit.

The new typed tables are independently exact: 80 bytes at ITCM
`0x5cb8..0x5d08` and 524 bytes at flash `0x0800352c..0x08003738`.
These are data, not executable recovery percentages.

## Timer SDK and motor hardware initialization

The flash bridges `0x080031fc..0x0800326a` route the motor hardware
initializer to these ITCM bodies:

| Function (`gd_motor_timer_` prefix) | Stock start | Full bytes | Candidate bytes |
|---|---:|---:|---:|
| `deinit` | `0x4f28` | 504 | 504 |
| `defaults` | `0x5850` | 20 | 20, exact |
| `init` | `0x5138` | 448 | 448, exact |
| `oc_config` | `0x4a10` | 820 | 780 |
| `oc_mode` | `0x4d48` | 104 | 88 |
| `oc_shadow` | `0x4dd8` | 94 | 102, standalone |
| `oc_pulse` | `0x4db0` | 34 | 32 |
| `master_slave` | `0x5548` | 28 | 28, exact |
| `master_output` | `0x5538` | 12 | 12, exact |
| `input_trigger` | `0x52f8` | 540 | 528 |
| `slave_mode` | `0x55a0` | 682 | 700, standalone |

The existing `mclib_hardware.h` types retain the 24-byte timer and 12-byte
output-compare stack layouts. Defaults leave the two padding halfwords
untouched (`0x5854`, `0x585e`). Initialization preserves timer-dependent
alignment/direction, auxiliary-period, clock-division and repetition-register
selection, then raises the update-event bit at `0x52ee..0x52f4`.

OC configuration accepts channels 0–3; mode/shadow/pulse accept 0–3 and 16–19.
Invalid channels return without a register access. Clear and set transactions
remain separate volatile read/modify/write pairs. Raw parameter fields are not
silently narrowed to their documented single-bit meanings. Complementary and
idle-state writes vary with both timer identity and channel.

`gd_timer_channel_offsets[20]` is actual read-only C data. Entries 4–15 really
contain `0x34`, even though the pulse helper rejects them with its `0xf000f`
membership mask. Keeping the full 80-byte object avoids inventing a shorter
table that would change its observed extent.

The routing helpers use three words per slot at SYSCFG `0x58000500`.
Unknown timer addresses select slot zero; there is no early invalid-timer
return. Both helpers always read all three initial words (`0x5446/5450/5454`
and `0x5704/5710/5714`), then retain the observed conditional reloads.
Slave-mode relocation may clear a lower field and still check upper fields
afterward (`0x5794..0x57ac`). Those subsequent volatile reads must not be
optimized out at source level. Out-of-range raw modes use ARM register-shift
semantics: the low eight count bits are used, and counts at least 32 produce
zero. The C helper expresses that behavior explicitly, not an invented API
validation rule or an undefined C shift.

`check-gd-timer-vendor.py --self-test` passes 7,483 stock-versus-candidate
execution cases. It compares ordered MMIO accesses, reset-call arguments and
order, configuration bytes/padding, preserved r4–r11/SP, and stack guards.
Cases cover all 22 known timers, unknown timer inputs, invalid channels,
repetition-count boundaries, individual/combined/reserved routing bits and
large raw mode values. Registers are modeled memory; these tests do not prove
physical peripheral timing, asynchronous register changes, or interrupt
interleavings. Seven functions remain byte-unmatched despite this result.

Deinitialization still calls the real reset helpers through ITCM veneers
`0x5b30` and `0x5b3a`; its remaining differences are terminal switch-block
ordering. Existing motor timer-enable/channel-enable bodies are reused,
not duplicated in this module.

## DMA and interrupt/system controls

The DMA SDK reconstruction covers `0x2a40..0x2b26` and `0x2c90..0x2d74`,
excluding the previously recovered IRQ helpers. Enable and circular-enable
are exact, 18 bytes each. Deinit, flag clear, interrupt enable and full init
have complete source but remain unmatched.

DMA channels have a 24-byte register stride. Flag groups use the observed
six-bit/eight-bit spacing; flags are ORed into the clear registers as stock
does, not replaced with an assumed write-one-to-clear shortcut. Initialization
keeps raw configuration words, the SDK's inverted increment choices, the
special nonzero/non-one peripheral-increment branch, and the OR-based DMAMUX
address calculation. These sources assume the hardware channel domain 0–7;
they do not establish behavior for arbitrary invalid channel shifts.

Crucially, recovering the consumer does not resolve the hardware caller's
uninitialized DMA field: stack configuration member `control_018` at +24 is
read to choose control bit 8. No zero/default has been fabricated. The full
motor hardware initializer remains unmatched, and its matching 181-target
call sequence does not validate these indeterminate arguments or timing.

`interrupt_control.c` implements priority enable at flash `0x08002010`
(102-byte stock span), priority grouping at `0x08002078` (20 exact bytes),
and SYSCFG route selection at `0x08002ed0` (58 bytes, 52 matching).
It preserves AIRCR key writes, fallback grouping, byte priority stores,
word interrupt-enable stores, and the SYSCFG lock-bit early return. Raw
arguments and volatile clear/reload/OR behavior are retained without added
range checks. No independent exhaustive hardware model is claimed here.

## Analog inputs and buttons

Analog objects have the observed 44-byte layout; the ADC handle at offset 32
is two words, and sampling state is at offset 42. The timer callback at
`0x7c0` polls, accumulates halfword samples, checks configured ranges and wakes
the report task. Shutdown (`0x868`, 102 bytes) and task (`0x8d0`, 196 bytes)
are exact. Config/query are complete but unmatched; this board has no proven
levelBoard-style analog debug-global store to add.

ADC cancellation (`0x2e98`), read (`0x2ed8`) and sampling (`0x2ef8`) are
exact. They retain the ADC2 status/selection checks, channel-zero cache
exception, and duplicate data-register reads. Setup at `0x2f30` is 219/220
positional bytes, not exact. Its 21-entry pin map includes pin 254 at channel
18 and repeated zero entries; no extra pin validation is inserted. The DWT
delay at `0x5ae0` is exact over 60 bytes and enables DWT only when the trace
enable bit was originally clear, then uses a signed wrapping deadline.

The cache symbol `gpio_adc_channel_samples` is still an explicit RAM binding
at `0x24008b18`. Its allocation extent is not proved: channel 18 writes at
base +36, while separately known inhibit bytes lie at base +32/+33. Defining
an assumed 21-element array would overlap those real objects. This unresolved
layout must not be disguised as an oversized zero-filled global.

Buttons retain a 32-byte OID prefix followed by 12-byte GPIO handles. The
timer callback at `0x998` performs two-sample debouncing, queues up to eight
report bytes, and drives byte-wrapping retransmission state. The report task
at `0xa58` is exact (180 bytes), as are add at `0xc20` (112 bytes) and config
at `0xd58` (76 bytes). Event, ACK and query remain unmatched. The source keeps
the IRQ-protected report operations, eight-button limit, byte-width decoded
pin/pull arguments, and retransmit-count validation.

The one-byte `analog_wake` and `buttons_wake` objects at `0x24003814/15`
now have real typed zero-initialized storage. That does not determine the
separate ADC cache extent.

## Motor lookup trigonometry

`mclib_sincos` spans flash `0x08002970..0x08002b50` (480 bytes) and
`mclib_sine` spans `0x08002b50..0x08002c48` (248 bytes), including their
constant pools. Neither is byte-exact. Sincos is 484 bytes and remains
standalone because its last literal overlaps the next stock function; sine
fits but has only 85 positional matching bytes.

The typed 131-float quarter-wave table includes both interpolation guards:
element 1 is zero, element 129 is one, and elements 0/130 extend the table
past those boundaries. The next bytes at `0x08003738` are ASCII, not more
float samples. Hexadecimal literals preserve the existing rounded values;
the source does not recompute them using host libm.

Wrapping repeatedly rounds using stock's `0x40c90fdb` full-turn constant,
while quadrant boundaries use their observed distinct ULP values. Signed
conversion and independent truncation produce table indices and interpolation
fractions. Sincos receives angle in s0 and output pointers in r0/r1, computes
both outputs before storing sine then cosine, and retains that aliasing order.
Non-fused interpolation operations must not be replaced with FMA or libm.
The sine candidate speculates reflected-quadrant arithmetic where stock
branches; complete numeric/FPSCR equivalence remains unproved. NaN/infinite
and sufficiently large finite wrapping inputs can fail to terminate, as stock
does; no artificial bounds or fallback result has been introduced.

## Follow-on configuration and PWM source

The subsequent source-integration pass also adds
`recovered/config_finalize.c` and `recovered/mclib_pwm_vendor.c`; these are
separate from the 38-body subtotal above. Configuration finalization at ITCM
`0x1460` has a complete 324-byte stock span and a 308-byte candidate, still
unmatched. Its inlined allocation/move-reset paths keep the second memory-end
check, rounded allocation pointer, zero fill and free-list tail reloads.

The PWM/current interface adds ten complete bodies over 548 stock bytes,
seven exact over 230 bytes. Exact functions include current polarity at
`0x3a60` (4 bytes), signed-current acquisition at `0x3a68` (112 bytes), PWM
enable at `0x3b08` (48 bytes), OC defaults at `0x4eb8` (10 bytes), additional
pulse at `0x4980` (14 bytes), fast mode at `0x49f8` (24 bytes), and primary
output at `0x5568` (18 bytes). Current acquisition reads signed halfwords at
sample offsets +0/+4, applies the observed scale and signed 0.04 offset, and
does not replace the arithmetic with a fused operation.

PWM channel initialization (`0x3c20`, 98 bytes), whole PWM initialization
(`0x3c88`, 116 bytes), and additional OC mode (`0x4990`, 104-byte stock span)
remain unmatched. Initialization configures four channels and enables the
primary-output gate only for `0x40010000/0x40010400`; it does not start the
timer or enable its channels. No new storage is fabricated. The fast-mode
helper retains the unchecked variable-shift source, so its exact target bytes
do not establish portable C behavior for invalid channel arguments.

With the polarity setter now present at `0x3a60`, the older 76-byte current
calibration candidate starting at `0x3a18` overlaps real neighboring source.
It is now explicitly standalone-only. This exposes a previously missing
neighbor rather than changing the calibration source or compiler options.

## Debug scope and newly proven storage

`recovered/debug_scope.c` adds exact JScope initialization at flash
`0x08000b38..0x08000b78` (64 bytes including its inline channel name).
It configures RTT up-channel 1 with a 1,024-byte buffer at `0x24002e8c`,
then tail-calls the observed peripheral-clock enable.

The complete RTT configuration function at `0x08000550..0x0800061c`
is 204 stock bytes; its 200-byte candidate remains unmatched. Lazy setup
clears the 168-byte control object, initializes terminal descriptors,
executes a DMB, publishes the reversed identifier, and executes another DMB.
Only afterward does it reject a channel above 2. Valid updates save BASEPRI,
set it to 32, update the descriptor and restore BASEPRI. Channel zero changes
flags only; channels 1/2 replace descriptor fields and clear the read/write
offsets. Store grouping, block order and register scheduling differ; no
independent execution-model equivalence is claimed for this helper.

The reversed identifier at `0x08003378` (16 bytes) and terminal name at
`0x08003738` (9 bytes) are independently exact typed constants. The latter
also confirms the sine table's upper boundary. Four now-proven BSS objects
cover the JScope buffer, RTT control, terminal up buffer (1,024 bytes) and
terminal down buffer (16 bytes). Together with the analog/button wake flags,
the current BSS gate covers 49 objects and 23,675 bytes; another 10,301 bytes
of the stock zero region remain unclassified. None of that zero storage is
counted as executable or initialized flash data.

## Reproduction and interpretation

From the repository root:

```sh
python3 tools/check-gd-timer-vendor.py
python3 tools/check-gd-timer-vendor.py --self-test
python3 tools/check-gd-timer-data.py
python3 tools/check-gd-dma-vendor.py
python3 tools/check-gd-interrupt-control.py
python3 tools/check-gd-analog-in.py
python3 tools/check-gd-buttons.py
python3 tools/check-gd-trig.py
python3 tools/check-gd-trig-data.py
python3 tools/check-gd-config-finalize.py
python3 tools/check-gd-pwm-vendor.py
python3 tools/check-gd-debug-scope.py
python3 tools/check-gd-debug-scope-data.py
python3 tools/check-gd-recovery.py
```

Byte gates intentionally return nonzero while any complete span differs.
`work/mainBoardGD-*/results.json` records canonical source/compiler provenance
and full byte comparisons. The timer model report is separately stored in
`work/mainBoardGD-timer-vendor-model.json`; its successful behavior comparison
does not override unmatched byte rows. Source-built initialized RAM and the
independently exact 3,284-byte scatter/load-data artifact remain separate
evidence, not proof of runtime helper equality or a bootable whole image.

The final canonical regression for this session passes 26/58 gate processes;
remaining failures are the explicitly recorded byte mismatches. The partial
link contains 173/272 exact C function spans (9,920 bytes), six exact
architectural assembly spans (208 bytes), and 445/445 independent
section-parity checks, with 87 structural vector/veneer exclusions. All 44
inventory reports are fresh and have no evidence conflicts. The deduplicated
runtime-address union is 27,524 exact bytes excluding zero storage; it includes
the initialized RAM, not an additional copy of its compressed load bytes.
Neither that union nor the successful parity check is whole-image equality.
