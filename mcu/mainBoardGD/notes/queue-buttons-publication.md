# Queue and button-report publication recovery

Measured 2026-09-09 with the unchanged shared ATfE 22.1.0 configuration.
The common-tail reconstruction of `move_queue_push` is **40/40 bytes exact**.
Button-query initialization improves from **95/124 to 98/124 matching bytes**
at its unchanged complete extent, but remains nonexact. These are actual C
source changes, not compiler-option changes or modeled-only replacements.

## Queue insertion: common pointer destinations

`move_queue_push` occupies ITCM `0x3e58..0x3e80`, with no literal pool.
The previous straightforward branch-local assignments compile to 30 bytes
with only 1/40 positioned bytes matching. The candidate reverses the nonempty
queue's link/last stores and merges empty-queue publication into a `STRD`.

Stock instead snapshots `queue->first` at `0x3e5a`, clears `node->next` at
`0x3e64`, selects two destination pointers and a boolean return value in its
branches, then uses two common stores at `0x3e78/0x3e7a`:

| State | First destination | Second destination | Return |
|---|---|---|---:|
| Nonempty | old `queue->last->next` | `queue->last` | 0 |
| Empty | `queue->last` | `queue->first` | 1 |

The adopted `recovered/move_queue.c` describes precisely those destinations
using ordinary `struct move_node **` locals. It retains the initial snapshot
before clearing the node, and performs the two stores after the branches.
This first grounded hypothesis reproduces every stock instruction and all
40 bytes at the correct entry. It introduces no volatile qualifier, lock,
function attribute, assembler instruction or register constraint. The source
spelling explains stock's shared tail; exact original variable names remain
unknown.

The complete canonical base gate improves from 38/45 exact functions and
2,256 exact-span bytes to **39/45 and 2,296 bytes**. All other 44 candidate
section hashes, including the preceding 38 exact functions, are unchanged.
The still-nonexact setup/reset and scheduler helpers are not counted as exact.

## Button query: staged report initialization

`command_buttons_query` occupies ITCM `0x0c90..0x0d0c` (124 bytes), including
its error string and alignment. Its public argument layout is unchanged.
After OID lookup and timer deletion, stock initializes timing and pressed
state, then performs these stages:

1. Publish `ack_count=0` and `retransmit_state=0xfe` as the adjacent halfword
   at object offset `0x1b`, instruction `0x0cba`.
2. Read the full retransmit argument word at `0x0cc0`.
3. Clear the separate `report_count` byte at `0x0cc2`.
4. Store the low retransmit byte at `0x0cc6`, rejecting argument bit 7.

The earlier source chained ACK/report-count zeroing, allowing report count to
be cleared before the header publication. The adopted `recovered/buttons.c`
separates the header assignments, snapshots `args[3]` into a `uint32_t`, then
clears report count and stores the retransmit byte. The stored count still
truncates to eight bits, and its rejection condition is unchanged for every
32-bit argument. No IRQ primitive is added to this body; timer deletion and
conditional re-addition retain their observed call boundaries.

Three bounded hand hypotheses were compiled from complete source modules:

| Hypothesis | Candidate / stock extent | Matching bytes | Decision |
|---|---:|---:|---|
| Baseline | 124 / 124 | 95 | superseded |
| Header first, full argument snapshot, then report-count clear | 124 / 124 | 98 | adopted |
| Same, with a narrow volatile report-count publication | 124 / 124 | 98 | unnecessary; identical emitted bytes |
| Same, with explicit two-byte header copying | 124 / 124 | 98 | unnecessary; identical emitted bytes |

The simpler first hypothesis preserves all five other button section hashes.
The button profile remains **3/6 exact, 368 exact-span bytes**. Argument/object
register allocation and zero-constant scheduling still differ from stock;
the correct field-write order does not make this function exact. No source
permutation workers were used for either target.

## Focused execution checks and limits

Scratch records are retained at `/tmp/gd-publication-shapes.nDswS7/`. These
temporary artifacts are diagnostic rather than durable build dependencies:

```sh
python3 /tmp/gd-publication-shapes.nDswS7/check_queue_model.py
python3 /tmp/gd-publication-shapes.nDswS7/check_buttons_model.py
```

Both scripts verify current canonical source/compiler/stock hashes, linked
section and Thumb-symbol entries, complete sizes and candidate hashes before
executing stock and candidate instructions in Unicorn.

- Queue: **64/64 cases** across empty/nonempty states, varied queue addresses,
  random surrounding storage and random preserved registers. Empty queues
  deliberately retain arbitrary stale last pointers. An independent oracle
  checks every ordered word read/write, initial first-pointer snapshot before
  node clearing, return value, complete RAM/stack canaries, r4-r11, SP and
  return PC. There are no mocked callees.
- Button query: **768/768 cases** cover all 256 retransmit low bytes, unrelated
  random high bits, zero/one/maximum rest intervals, random clock/invert/OID
  arguments and initial object bytes. Stock and candidate have identical
  ordered data reads, field-write widths/order, full RAM and call traces.
  An independent state oracle checks both pressed bytes, timing fields,
  report header/count, untouched padding/reports and bit-7 rejection.
  OID lookup, timer deletion/addition, error-string lookup and shutdown are
  explicitly mocked. Ordinary returns preserve r4-r11/SP/return PC; a
  noreturn shutdown is checked at its boundary with the saved caller frame,
  not incorrectly required to restore the normal-return stack.

These checks do not execute the scheduler's timer internals or establish
interrupt interleavings, physical timing, aliased button argument/object
behavior, or complete firmware bootability. No model success is substituted
for the still-failing button byte gate.

Rebuild the durable canonical byte comparisons from the repository root:

```sh
python3 tools/check-gd-base.py
python3 tools/check-gd-buttons.py
```

Both overall exits remain nonzero because their recorded unmatched bodies
remain open. The current scoreboards own subsequent integration totals.
