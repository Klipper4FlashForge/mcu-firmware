# ADC sample-cache RAM layout

Stock audit on 2026-09-09. The cache store addresses and neighboring GPIO flags
are established, but the original cache object's size is not. The existing
incomplete binding `gpio_adc_channel_samples` at `0x24008b18` remains justified;
there is not enough evidence to define a 16-, 19- or 21-element C array without
assuming an original overflow or an undocumented aliasing layout.

All code addresses below are ITCM unless explicitly prefixed with a flash
address. Instruction evidence comes from `work/itcm.lss`, checked against the
stock ITCM payload; Ghidra is navigation evidence only. No source, BSS profile
or coverage scoreboard is changed by this audit.

## Actual writers and callers

`gpio_adc_read` occupies `0x2ed8..0x2ef4`. It receives the two-word ADC handle
in r0/r1: peripheral base and full-width channel. It writes `0xffffffef` to the
status register, then tests channel for zero at `0x2ede`. For nonzero channels,
the `0x2ee4` word read from peripheral `+0x64` is truncated by the `STRH` at
`0x2eea` and stored to:

```text
0x24008b18 + (channel << 1), using ARM 32-bit address arithmetic
```

It reads the peripheral data register again at `0x2eee` and returns that second
read's low halfword. Channel zero bypasses the cache store and performs only
the final data-register read. The return is not a load from the cache.

`gpio_adc_cancel_sample`, `0x2e98..0x2ed2`, saves the interrupt state, checks
status bit `0x10`, and compares the selected register's low five bits with the
full channel. Only a match clears status. A nonzero matched channel performs
the same cache update at `0x2ec4`, using the data read at `0x2ebe`; `0x2ec8`
performs the extra discarded data read. It restores the saved interrupt state
through the tail call at `0x2ece`. Thus cancellation additionally excludes
channels above 31 through its hardware-selector comparison, but the read
helper has no such check.

The observed direct callers are:

| Caller | Call site | Handle source |
|---|---|---|
| `analog_in_event` | `0x7d8` to read | two words loaded from OID offsets `+32/+36` at `0x7d4` |
| `analog_in_shutdown` | `0x8a4` to cancel | same handle offsets, loaded at `0x8a0` |
| `command_query_analog_in` | `0x1a44` to cancel | same handle offsets, loaded at `0x1a40` |
| `command_config_analog_in` | `0xd22` to setup | low pin byte loaded from the argument word at `0xd1c` |

Configuration copies setup's returned peripheral/channel words into OID
offsets `+32/+36` at `0xd42/0xd46`. Query updates sampling parameters, not the
handle. No ordinary application reader of the cache is identified. The two
explicit cache-base materializations, at `0x2eba/0x2ec0` and
`0x2ee0/0x2ee6`, feed the two stores above. Generic debug-memory access does not
identify a cache extent or provide an additional cache-specific consumer.

## Which channel indices setup can actually return

The byte table occupies `0x2fe0..0x2ff5`:

```text
34, 35, 89, 87, 85, 83, 90, 88, 86, 84, 32, 33,
0, 0, 0, 0, 0, 0, 254, 0, 0
```

The loop at `0x2f3c..0x2f46` takes the **first** matching byte. Repeated zero
entries therefore select channel 12, not channels 13–17 or 19–20. A miss
shuts down; no fabricated fallback channel is needed. The resulting handle
uses ADC2 at `0x40012c00` and the matched index, stored at `0x2fd6`.

| Pin byte | Channel | Cache halfword address |
|---:|---:|---|
| 34 | 0 | no cache write |
| 35 | 1 | `0x24008b1a` |
| 89 | 2 | `0x24008b1c` |
| 87 | 3 | `0x24008b1e` |
| 85 | 4 | `0x24008b20` |
| 83 | 5 | `0x24008b22` |
| 90 | 6 | `0x24008b24` |
| 88 | 7 | `0x24008b26` |
| 86 | 8 | `0x24008b28` |
| 84 | 9 | `0x24008b2a` |
| 32 | 10 | `0x24008b2c` |
| 33 | 11 | `0x24008b2e` |
| 0 | 12 | `0x24008b30` |
| 254 | 18 | `0x24008b3c` |

Pin 254 is a real setup path: `0x2fba..0x2fc6` enables the peripheral's
`0x800000` control bit and skips ordinary GPIO configuration. Its channel-18
cache store cannot be dismissed as a malformed handle. It writes beyond,
not into, the two known inhibit bytes. The normal setup path does not return
channel 16, which would write over both flags.

## Adjacent objects and unresolved gaps

Intervals are half-open. A location that has no setup-generated access is not
necessarily padding or an absent object.

| RAM interval | Evidence |
|---|---|
| `0x24008b14..0x24008b16` | separate serial transmit maximum/position bytes |
| `0x24008b16..0x24008b17` | trigger-sync wake byte |
| `0x24008b17..0x24008b18` | unclassified byte; alignment is plausible |
| `0x24008b18..0x24008b1a` | cache-base/index-zero location; both cache writers skip index zero |
| `0x24008b1a..0x24008b32` | 12 consecutive halfword destinations for channels 1–12 |
| `0x24008b32..0x24008b38` | raw indices 13–15; not returned by setup |
| `0x24008b38..0x24008b3a` | two independently addressed GPIO inhibit bytes; also the raw index-16 destination |
| `0x24008b3a..0x24008b3c` | raw index 17; not returned by setup |
| `0x24008b3c..0x24008b3e` | actual setup-generated channel-18 halfword destination |
| `0x24008b3e..0x24008b40` | raw index 19; not returned by setup |
| `0x24008b40..0x2400b340` | unclassified zero region; its first halfword is the raw index-20 destination |

`gpio_out_write` writes boolean pin-`0x72` state to `0x24008b38` at `0x3766`
and pin-`0x73` state to `0x24008b39` at `0x377a`. These are real one-byte
objects, not cache padding. `gpio_out_toggle_noirq` loads the first at
`0x3332`, and only if it is zero loads the second at `0x33b8`. Both must be
zero, and the physical output must be high, before the logical motor-step
dispatch. Physical GPIO accesses and direction dispatch have their separate
observed behavior; the two bytes are not general motor-enable flags.

A stock-only Unicorn check uses different first/second ADC register values
(`0x1234abcd`, `0x89ab3456`) to distinguish cache and return semantics:

| Handle channel | RAM effect | Return | Inhibit bytes initially `a5 a5` |
|---:|---|---|---|
| 0 | none; one ADC data read | `0xabcd` | unchanged |
| 12 | halfword `0xabcd` at `0x24008b30` | `0x3456` | unchanged |
| 16, raw non-setup handle | halfword at `0x24008b38` | `0x3456` | become `cd ab` |
| 18 | halfword at `0x24008b3c` | `0x3456` | unchanged |
| 20, raw non-setup handle | halfword at `0x24008b40` | `0x3456` | unchanged |

This bounded check confirms the instruction-derived addresses and duplicate
reads. It neither proves an original C allocation nor validates physical ADC
side effects. No raw-handle case is claimed to arise through normal setup.

## Why the declaration remains incomplete

A 16-halfword cache ending exactly at `0x24008b38`, followed by the two flags
and six alignment bytes, is consistent with the address spacing. Under that
hypothesis the genuine channel-18 store is out of bounds and lands in putative
padding. The binary cannot prove this is the original declaration or an
original bug. A contiguous cache large enough for channel 18 instead overlaps
the real inhibit objects. That alternative needs explicit alias/containing-
object evidence, which is also absent. A write destination by itself is not
an allocation-size witness.

The initial stack pointer is `0x2400b340`, present in the vector table and the
reset literal at flash `0x080003b4`; it is also the scatter zero-region end.
The distance from `0x24008b40` is exactly `0x2800` (10,240 bytes), suggestive of
a 10 KiB stack after aligned globals. There is no independent stack-base
reference or reservation-size proof in this audit. Do not turn this arithmetic
into a `stack[10240]` declaration or label the channel-18 destination harmless
padding on that basis.

The reference search covers explicit MOVW/MOVT address constructions in the
decoded ITCM/flash code and every byte-aligned little-endian address word in
flash before compressed data, ITCM and initialized RAM. The cache/flag
constructions above are the only direct ones found. Only the two initial-SP
words refer directly to the later `0x24008b40..0x2400b340` range. This is not
an exhaustive proof against indirect address arithmetic or externally supplied
debug addresses.

The next decisive evidence would be an original linker map, unstripped object
with a symbol size, SDK/application source declaration, or a clearly bounded
initializer/access that establishes the cache's allocation. Until then, retain
the incomplete external binding and the two proven byte objects. Preserve raw
store behavior; do not add a channel bound, merge the flags into an assumed
array, or claim extra zero-state coverage. This uncertainty does not block
source shaping or the already verified initialized-RAM image.

See [peripheral/input recovery](peripheral-input-recovery.md),
[GPIO trigger-sync semantics](gpio-trsync-recovery.md), and
[runtime storage evidence](runtime-recovery.md) for the surrounding paths.
