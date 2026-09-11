# What the remaining coverage gaps actually contain

Audit: 2026-09-09, against the saved canonical inventory reporting 1,107 ITCM
gap bytes and 1,579 flash gap bytes. Stock MD5:
`fb64911bac422a27d7ed7fab3597603f`.

There is **no unclassified nonzero function body in these gaps**. Their
nonzero contents are the already-verified vector table, already-verified
cross-region veneers, and the separately verified scatter records. All other
gap bytes are zero. This is a classification of a saved coverage snapshot,
not a claim that every source reconstruction, function boundary, or whole
firmware image is correct.

## Reproducible classification

```sh
python3 tools/report-gd-gaps.py --self-test
python3 tools/report-gd-gaps.py --out work/mainBoardGD-gaps.json
```

The report partitions every input gap without overlap or discarded bytes.
It records each range's stock SHA256, neighboring source-check evidence,
and classification. It re-extracts vectors/veneers from the stock instruction
templates, verifies their actual partial-ELF sections against stock, and
checks the separate source-built scatter artifact. The inventory, partial
report/ELF and scatter report hashes identify the exact audit inputs.

| Inventory gap category | ITCM bytes | Flash bytes |
|---|---:|---:|
| Exact generic veneers in the partial ELF | 410 | 450 |
| Exact symbolic vector table in the partial ELF | 0 | 932 |
| Exact scatter records in the separate load-data artifact | 0 | 48 |
| Observed zeros consistent with alignment | 697 | 149 |
| Unclassified nonzero contents | 0 | 0 |
| Total saved inventory gaps | 1,107 | 1,579 |

The 860 veneer bytes are executable bridges, but not missing C functions.
Their exclusion from the source inventory is deliberate: the partial link
already emits the generic symbolic `movw ip; movt ip; bx ip` construction.
Do not add them as independently recovered business-logic functions.

## Large apparent holes

All ranges below are half-open execution-address intervals, not file offsets.

| Range | Interpretation and end evidence |
|---|---|
| Flash `0x08000000..0x080003a4` | 233 vector words including initial SP; the next address is the runtime entry, not another vector. The symbolic C table is exactly 932 bytes in the partial ELF. |
| ITCM `0x5b1c..0x5cb6` | 41 ten-byte veneers. The final bridge begins `0x5cac` and ends with `bx ip` at `0x5cb4`. |
| ITCM `0x5cb6..0x5cb8` | Two zero bytes between that final bridge and the typed timer-offset array. |
| Flash `0x08003198..0x0800335a` | 45 ten-byte veneers. The final bridge begins `0x08003350` and ends with `bx ip` at `0x08003358`; the copy helper begins immediately at `0x0800335a`. |
| Flash `0x08003741..0x08003744` | Three zero bytes after the exact nine-byte terminal-name string at `0x08003738`. |
| Flash `0x08003744..0x08003774` | Three 16-byte scatter records, not executable code. Dispatcher literals at `0x080004e4/0x080004e8` delimit this exact table. |
| Flash `0x08003774..0x08003778` | Four zero alignment bytes before the compressed initialized-RAM payload. Already included in the independently exact load-data artifact. |

The scatter records describe decompression into `0x24000000` (11,912 bytes),
copy into address zero (28,120 ITCM bytes), and zero fill at `0x24002e88`
(33,976 bytes). Their helper entries are `0x080004ec`, `0x0800335a`, and
`0x0800336a`. The separately verified source-built load-data artifact spans
`0x08003744..0x08004418`; only its first 52 bytes lie inside this inventory's
flash denominator. The compressed payload is not additional uncovered code.

## Small zero gaps and boundary caution

The saved inventory has 164 ITCM gap intervals and 39 flash gap intervals.
After splitting out known structures, every residual zero interval is at
most six bytes and ends on an eight-byte boundary, except the four-byte
boundaries at `0x655c`, `0x0800338c` and `0x08003744`. This strongly supports linker alignment around
the already-delimited functions/data, rather than another undiscovered body.

Representative instruction-boundary evidence:

- Flash `0x080004c4` is the longjmp return; `0x080004c6..0x080004c8`
  contains one zero halfword before the scatter dispatcher.
- Decompression returns with `pop {r4,r5,r6,pc}` at `0x08000548`;
  `0x0800054a..0x08000550` is six zero bytes before RTT configuration.
- The last ITCM veneer returns through `bx ip` at `0x5cb4`; its following
  zero halfword does not belong to that ten-byte bridge.

Data-boundary examples require different language from function padding:

- `0x655a..0x655c`: two zeros after a generated protocol object, followed
  by the next object on a four-byte boundary.
- `0x68e6..0x68e8`: two zeros before the separately typed ACK encoder.
- `0x6dd7..0x6dd8`: one trailing zero after the parser-error string, ending
  the 28,120-byte ITCM execution region.
- Flash `0x08003388..0x0800338c`: four zeros after the 16-byte reversed
  RTT identifier, before the typed atan table on a four-byte boundary.

These are recorded as **zero alignment candidates**, not newly invented C
objects. Zero bytes alone cannot prove that the original compiler/linker had
no zero-valued object there. An original scatter script or stronger section
provenance would settle that distinction. A future full-image layout emitter
should preserve the observed fill separately from typed objects and code.

Every non-null vector and every veneer target falls inside an existing
source-covered function/assembly span. This test includes the real function
at address zero; zero is not treated as an absent target. Default-handler
vectors can target an interior label of the existing reset/runtime assembly
span, so they must not be counted as hundreds of unrecovered bodies.

## Highest-value remaining code work

The important unfinished bodies are already covered by standalone or
unmatched source gates; they are not part of the gap totals above. Runtime
and library exactness remains a practical prerequisite for a complete image.
The following bounds come from stock entry references and terminating
instructions, not Ghidra's reported byte count alone.

| Entry / full end | Bytes | Evidence and remaining work |
|---|---:|---|
| `0x080003f4..0x08000434` | 64 | Shared AEABI copy/move implementation, reached through ITCM veneers `0x5b4e` and `0x5b80`. Backward-overlap return at `0x040e`, forward return at `0x0432`. Actual C exists; fitting/exact output is unresolved. |
| `0x08000434..0x08000442` | 14 | AEABI fill body; byte truncation at `0x0434`, return at `0x0440`. Its argument order is destination/size/value, not C memset's argument order. |
| `0x08000442..0x08000446` | 4 | AEABI clear entry: sets r2 to zero then tail-branches to `0x0434` at `0x0444`; the following C memset entry is distinct. |
| `0x08000446..0x08000458` | 18 | C memset adapter calls the AEABI fill body at `0x0450` and restores the original destination before its `0x0456` return. |
| `0x08000458..0x08000474` | 28 | strcmp, veneer target `0x5b8a`; byte comparisons and return at `0x0472`. A fitting source candidate exists but is unmatched. |
| `0x08000474..0x08000488` | 20 | memchr, veneer target `0x5b58`; shared found/not-found return at `0x0486`. Zero length must not read the source. |
| `0x080004ec..0x0800054a` | 94 | Scatter decompressor, selected by the first record; final return at `0x0548`. The zero-output call still processes one token. Existing complete C/model is not byte-exact. |
| `0x0800335a..0x08003368` | 14 | Scatter word copy. Entry branch reaches count test at `0x3362`; return at `0x3366`. The separate no-op at `0x3368` is not padding or part of this helper. Concurrent follow-up now supplies exact assembly, as noted below. |
| `0x0800336a..0x08003378` | 14 | Scatter word zeroing. Return at `0x3376`; the reversed RTT identifier begins at `0x3378`. Concurrent follow-up now supplies exact assembly. |

During this audit, the runtime agent identified the copy/zero helpers as
assembly-origin `handlers.s` in the local AC6.16 microlib archive and added
`recovered/scatter_handlers.S` with 28/28 exact bytes. The separate
`check-gd-scatter-handlers.py` gate and 36-case model pass. This changes their
remaining-work status, not their bounds or the gap classification: these
spans were already source-covered by unmatched C. The other memory/string
bodies and `lz77c.c` decompressor have C-origin library metadata; the new
assembly exception must not be generalized to those C functions.

Other high-impact standalone constraints have equally concrete neighbors:

- ITCM timer shadow `0x4dd8..0x4e36` includes its 20-entry branch table;
  return at `0x4e34` precedes two alignment bytes and channel-enable at
  `0x4e38`. Its then-current 102-byte candidate cannot fit the 94-byte span.
- Timer slave mode `0x55a0..0x584a` ends with a return at `0x5848`;
  six zero bytes precede defaults at `0x5850`. The then-current candidate
  is 700 bytes versus 682 stock bytes.
- Motor sine/cosine `0x08002970..0x08002b50` includes its trailing constants;
  the next sine function starts at `0x08002b50`. Its then-current 484-byte
  candidate exceeds the full 480-byte slot. Do not cut the last constant.
- Current calibration `0x3a18..0x3a5c` has four bytes of alignment before
  the exact polarity setter at `0x3a60`. The then-current 76-byte candidate
  overlaps that real setter and must remain excluded until it fits.

These sizes are the audit snapshot, not promises about later source-shaping
results. Consult each canonical gate and the partial report's explicit
standalone-exclusion list after another compiler/source iteration.

## Consequence for the whole-image plan

The next phase is primarily exact matching, dependency/ABI validation, and
source-built layout integration, not searching the small gap totals for a
large missing SDK module. The gap audit does not reduce the tens of kilobytes
already covered by unmatched source. It also does not classify the remaining
zero-initialized RAM, prove the ADC cache extent, or validate physical boot
behavior. Those are separate unresolved obligations.
