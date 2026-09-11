# Source-only scatter compression

Session: 2026-09-09. The source-only `lazy-lex128` encoder reproduces the complete
**3,225/3,225 compressed bytes and 754/754 tokens exactly** from source-built RAM.
Earlier candidates remain reproducible diagnostics, not accepted alternatives.
This closes this image's initialized-RAM compression gate, not the entire
firmware reconstruction or the identity of armlink's original implementation.

## Inputs and provenance

The stock scatter entry at flash `0x08003744` describes:

| Property | Observed value |
|---|---|
| Compressed source | `0x08003778` |
| Expanded destination | `0x24000000` |
| Expanded size | 11,912 bytes, through `0x24002e88` exclusive |
| Decompressor | `0x080004ec`, 94 bytes |
| Bytes consumed by decompressor | 3,225 |
| Compressed end | `0x08004411` exclusive |
| Following alignment | Seven zero bytes before ITCM load source `0x08004418` |

The seven post-stream bytes are not part of the 3,225-byte compression target.
The helper implements the format decoded by
[`tools/scatterload.py`](../../../tools/scatterload.py); the assembly is available
in `work/flash.lss` at `0x080004ec..0x0800054a`.

The encoder input is **not the stock decompressor output**. It is
`work/mainBoardGD-partial/initialized-ram.bin`, assembled by
[`tools/build-gd-partial.py`](../../../tools/build-gd-partial.py) from the actual
linked candidate ELF sections. The builder checks that the sections partition
the complete RAM interval without gaps or overlaps and compares the result to
the independently expanded stock image. Its `results.json` records both hashes.

The source/layout contributions are:

- 8,568 bytes of readable retained `.ctr` strings and their final two zeros,
  compiled from `recovered/compile_time_requests.c`.
- 3,337 bytes from 16 typed objects in `recovered/state.c`.
- Seven bytes of explicit linker alignment, not invented C variables. The final
  four bytes at `0x24002e84` are an inferred RW/ZI boundary alignment; absence of
  references does not prove that the original source lacked an unused object.

The current source-built RAM SHA-256 is
`6bc60843941d8effde49e8bee2f19162710a5ad9d2ff0354fd64b9d0b4fee50f`.
The stock compressed stream SHA-256 is
`2d03ff555a6383f5d8d9a57631db39a38268aed6b71deaed85d0bffbdfe0b287`.

[`tools/gd_scatter_compress.py`](../../../tools/gd_scatter_compress.py) separates
encoding from diagnostics: `compress(data, hypothesis)` accepts only source RAM
bytes and a generic algorithm choice. It has no stock-image argument, stock
token table, address-specific exceptions, or oracle-selected match choices.
Only the later comparison and analysis read the stock compressed stream.

## Token format and limits

A token combines a literal run with an optional backwards match:

- Bits 0–1 hold literal count plus one. Zero means the following byte holds
  that count; up to 254 literal bytes fit in one token.
- Bits 4–7 hold match length minus two. Zero means a following byte holds that
  value; zero there denotes no match. Matches are 3–257 bytes long.
- Bits 2–3 encode distance bits 8–9 for distances below 768. Both bits set
  select a second distance byte, supporting distances through 65,535.
- Any count-extension bytes precede the literals; distance bytes follow them.
- Overlapping back-references are valid, including repeated-byte distance-one
  runs. Candidate matching only admits references strictly before the match.

The stock stream contains 754 match-bearing tokens. Its largest distance is
8,922, largest match is 257, and largest literal run is 34. The representable
limits above therefore require synthetic tests in addition to this image.

## Initial parsing hypotheses

The first three variants used an exhaustive three-byte match index, a
65,535-byte maximum distance and a 257-byte match cap. Equal-length matches chose
either the nearest or oldest occurrence. Neither tie policy matched stock.

The retained lazy rule is:

```text
emit one literal and reconsider when next_match_length > current_match_length + 1
```

The `+1` accounts for spending one input byte as a literal. All 58 stock literal
positions where a match of at least three bytes was available satisfy this
net-gain rule; none defer for an extension of only one byte. Conversely, eleven
stock matches are retained despite a one-byte-longer match at the next position.
An initial weaker `next > current` criterion was refined using this evidence;
the table below records the retained rule, not the earlier diagnostics.

| Hypothesis | Compressed bytes | Exact prefix bytes | Identical stock tokens | Stock match starts recovered |
|---|---:|---:|---:|---:|
| Greedy, nearest tie | 3,197 | 80 | 467 / 754 | 687 / 754 |
| Lazy, nearest tie | 3,140 | 93 | 516 / 754 | 753 / 754 |
| Lazy, oldest tie | 3,278 | 144 | 478 / 754 | 753 / 754 |
| Lazy, insertion-order binary tree | 3,275 | 144 | 482 / 754 | 753 / 754 |
| Lazy, 257-byte lexicographic keys | 3,229 | 3,063 | 746 / 754 | 753 / 754 |
| Lazy, complete suffix ordering | 3,229 | 3,063 | 745 / 754 | 753 / 754 |
| **Lazy, newest 128-byte lexicographic keys** | **3,225** | **3,225** | **754 / 754** | **754 / 754** |
| Stock | 3,225 | — | 754 / 754 | 754 / 754 |

The two initial lazy candidates have 754 tokens, but equal token counts are not
equality. At their 753 common stock match starts, 752 match lengths also agree. An
“identical token” here requires the same literal-start/match-start offsets,
literal count, match length and distance. Literal bytes come from the already
identical expanded image. Complete stream bytes and length remain the actual
gate; token counts are diagnostic only.

## Dictionary investigation and retained algorithm

**Evidence that motivated the search.** Of 754 stock matches, 753 use the globally longest
available match. Of those, 517 choose the nearest longest occurrence and 479 the
oldest; these sets overlap. Neither policy accounts for the shipped stream.
For example, at expanded offset `0x7b` (RAM `0x2400007b`), stock chooses a
four-byte match at distance 32 although distance 15 matches equally well. At
offset `0xcd`, the three-byte stock match uses distance 105 while the oldest
occurrence is distance 130. The initial matching prefix of the oldest policy
did not establish it as the original policy.

**One shorter-than-longest match.** At expanded offset `0x2a2c`
(RAM `0x24002a2c`), stock encodes a 132-byte match at distance one. A 257-byte
match at distance 792 is available in the previously initialized motor object.
This is the sole stock match shorter than the exhaustive search's maximum and
was the main remaining lazy-parse discontinuity.

**Rejected traversal.** An input-order binary search tree with 257-byte keys,
first-longest traversal selection, and newest replacement for identical keys
remained close to the oldest-distance result: 3,275 bytes, prefix 144. The tool
retains this as `lazy-bst`; it is not the chosen compressor.

**Lexicographic neighbors.** Sorting prior suffix keys and considering only the
immediate lower and higher neighbors was a much stronger hypothesis. Preferring
the lower neighbor on equal lengths yielded 3,234 bytes with prefix 222 in the
initial probe. Preferring the higher neighbor yielded 3,229 bytes with prefix
3,063. The latter prototype used 257-byte keys and retained duplicate entries;
it is reproducible as `lazy-lex257`. Complete suffix keys did not improve it
(`lazy-fullsuffix`, same size/prefix and one fewer matching token).

The 257-byte-key prototype differed at only seven stock match positions. The
first three were long zero runs at RAM offsets `0x270d`, `0x2a2c` and `0x2d3c`,
where stock selected distance one for lengths 139, 132 and 140. That suggested
dictionary keys shorter than the runs, with duplicate keys replaced by a
recent representative. The remaining differences also involved repeated
initialized motor data or the final zero suffix. A 128-byte key was the bounded,
power-of-two hypothesis derived from the shortest exceptional run of 132; this
was not an arbitrary parameter sweep.

The resulting source-only algorithm, `lazy-lex128`, is:

1. Insert every input position into a dictionary ordered by its next at most
   128 bytes. A duplicate key replaces its representative with the newest input
   position. References farther than 65,535 bytes expire.
2. Before inserting the current position, compare its key with the dictionary's
   immediate predecessor and successor. Compare the candidate bytes for up to
   257 bytes: **128 is a key limit, not a match-length limit**.
3. Select the longer match; select the successor when lengths tie. Require at
   least three bytes for a match.
4. Apply the already established net-gain lazy rule, then emit the literal/match
   token. Literal-only runs flush at the format limit of 254 bytes.

This produces stock's complete stream without address-specific cases. In
particular, repeated zero keys replace their older representatives, naturally
selecting distance one at `0x2a2c` despite a longer global match being available
in another key representative. All seven remaining discrepancies disappear.

The implementation precomputes dictionary choices in forward input order;
lazy lookahead sees the same dictionary state that sequential insertion would.
Precomputation uses input data only. The pure entry point is
`compress(data, 'lazy-lex128')`, also the default `compress(data)` behavior.

This establishes a compatible generic encoder for the observed image, not a
unique proof of armlink's internal data structure, key limit on other images,
or exact version. No additional key-length sweep was used to claim uniqueness.
The previous zero-run ambiguity is resolved by the retained model; there is no
remaining compressed-byte mismatch on the canonical source-built RAM input.

## Reproduction and review

From the repository root, after the partial builder has emitted fresh RAM:

```sh
python3 tools/gd_scatter_compress.py --self-test
python3 tools/gd_scatter_compress.py
```

The second command writes all seven retained candidate streams and
`work/mainBoardGD-compression/results.json`, including input/stock/source
hashes, token comparisons and stock-policy observations. It now exits with
status 0 and records `any_exact: true`, `canonical_hypothesis: "lazy-lex128"`
and the canonical dictionary rules. `tools/check-gd-recovery.py` runs this
exactness gate after the partial build. To isolate the retained algorithm:

```sh
python3 tools/gd_scatter_compress.py --hypothesis lazy-lex128
```

The exact candidate file is `work/mainBoardGD-compression/lazy-lex128.bin`.
Running a rejected hypothesis alone still exits with status 1. Merely producing
a stream that decompresses to the right RAM bytes does not pass the gate.

The built-in self-test passed for all seven algorithms on empty/short inputs,
incompressible data, repeated bytes, overlapping patterns and command strings.
Explicit token tests cover literal-count boundaries, match lengths 3/17/18/257,
distance boundaries 255/256, 511/512, 767/768 and 65,535, and invalid token ranges.
New synthetic tests explicitly verify newest replacement for identical 128-byte
keys, the greater-suffix tie rule rather than nearest distance, 257-byte matches
through a 128-byte key, dictionary expiry, and a 66,000-byte repeated input. None
of these tests needs stock firmware or its token choices.

The bounded token inspector rejects missing bytes, zero literal-count fields,
zero/before-start distances and output overruns; complete-stream comparison
also rejects trailing bytes. Additional review on 2026-09-09 checked six such
malformed streams plus trailing data, 90 deterministic randomized round-trips,
and agreement of both initial indexed tie policies with an independent exhaustive
matcher on those short inputs. The malformed-stream tests are now retained in
`--self-test`. No correctness defect was found in that review.
The historical stock decompressor itself is not a general hardened parser;
these gates use the known stock image and independently inspect candidate bounds.
