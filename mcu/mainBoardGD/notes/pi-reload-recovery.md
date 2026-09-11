# PI accumulator reload recovery

The PI step occupies flash `0x080020d0..0x08002144`, 116 bytes, followed by
four alignment bytes before PI reset at `0x08002148`. Under the unchanged
shared ATfE configuration, the recovered body improves from 33/116 matching
bytes with a 110-byte candidate, through an 88/116 intermediate, to
**116/116 bytes exact**. The motor gate now has 23/32 exact functions, 1,240
complete-span bytes. All 22 preceding exact motor functions are retained.

## Observed access and arithmetic

Stock computes error with VSUB, loads the integral gain and old accumulator,
publishes error at controller offset `0x24`, and uses non-fused VMLA for the
integral update. It stores that update at offset `0x1c` before independently
clamping it. An upper comparison takes the ordered greater-than branch;
the lower signed LT condition also clamps unordered/NaN values. Replacing
the latter with a normal C `<` comparison is not equivalent.

At `0x0800210e` stock loads the proportional gain, then explicitly reloads the
clamped accumulator at `0x08002112`. The next VMLA at `0x08002116` is again
non-fused. Output limits are distinct from integral limits, and the final
output is stored at controller offset `0x28`.

The prior C candidate forwarded the local accumulator instead of reloading
controller state. The adopted local volatile float view preserves that one
observed post-clamp access. It adds no arithmetic or dummy instruction and
does not make the entire controller layout volatile. Reset/configuration also
publish controller state; this reconstruction expresses the observed access,
not proof of the original application's C spelling.

The intermediate candidate still loads the output minimum before reloading
the accumulator, whereas stock loads that minimum at `0x0800211a`, after the
output VMLA. The final source snapshots this minimum through a second local
volatile float view after computing the output, then uses the snapshot in
the lower comparison and clamp. It adds no extra load: each value is read
once at its observed stage. The two explicit accesses prevent that hoist;
the compiler then also selects stock's registers, producing the complete
116-byte match. Source arithmetic and NaN routing remain unchanged.

## Three bounded source hypotheses

All experiments use the common flags, exact entry and complete code span:

| Shape | Candidate bytes | Matching bytes |
|---|---:|---:|
| Original source | 110 | 33/116 |
| Explicit post-clamp accumulator reload | 116 | 88/116 |
| Volatile views for every accumulator access | 116 | 81/116 |
| Reversed source clamp-branch layout plus explicit reload | 116 | 88/116 |
| Follow-up: accumulator reload, then output-minimum snapshot | 116 | 116/116 |

The narrow post-clamp reload was adopted first. The full source was rebuilt in
scratch and through the canonical gate, retaining all 22 exact functions and
all other candidate section hashes. A subsequent independently verified
output-minimum snapshot in `/tmp/gd-pi-order.C5eZdp` closes the final 28 bytes
and passes the full canonical motor gate at 23/32 exact. No per-function flags,
register pinning, assembly, FP reassociation or changed state layout is used.

## Raw-byte permutation search and rejected improvement

The retained scratch directory is `/tmp/gd-pi-shapes.IHgi35`. Its minimal
baseline was independently compiled and compared to the full-source candidate
before searching. Both emit the same complete 116-byte function at the real
Thumb entry `0x080020d1`.

Starting from the 88/116 intermediate, the local permuter ran four workers
for 20,000 iterations in 169.81 seconds,
with 3,398 compile errors and zero internal errors. Its scorer compares all
positioned bytes, length, section/symbol address, symbol size and ELF entry.
Self-tests reject truncation, growth and moved entries; no normalization or
ignored literal pool is used. The baseline score is 28 differing bytes.

Exactly one distinct improvement was retained, scoring 27 differences, or
89/116 matching bytes. It changes the final `output > output_max` comparison
to `output_max < output`. The numeric branch result is equivalent, but the
reversed VCMP operands change FPSCR comparison flags. The stock/candidate
execution model rejects it on its first ordinary case: target and measured
zero, gains 0.5 and 0.125, initial integral 0.5, integral limits +/-10 and
output limits +/-20. Both return/store 0.5, but stock FPSCR is `0x80000000`
and the rejected candidate's is `0x20000000`. It is not adopted.

Enabled transformations match the bounded atan search: expression temporaries,
expansion, declaration/statement ordering, assignment splitting, commutative
rewrites, compound assignments and array aliases. Dedicated type/literal
randomization, deletions, dummy arithmetic and conditional-reference tricks
are disabled. Enabled passes can still introduce semantic defects, so a raw
byte improvement is not sufficient. The finite random search does not prove
that no exact C spelling exists; non-error iterations include cached outputs,
and the random seed stream is not pinned for exact replay.

## Reproducible stock-versus-candidate model

```sh
python3 tools/check-gd-pi-model.py
```

The checker reads the canonical motor report and actual isolated ELF. It
verifies source/header, compiler, stock and candidate hashes; full section and
symbol size; and the actual section, Thumb symbol and ELF entry addresses.
Stock and candidate execute their actual FP instructions in Unicorn; there
are no mocked operations or callees.

All 56,096 deterministic cases pass for the final exact candidate. They cross
all four rounding modes and FZ/DN
combinations with signed zeros, subnormal boundaries, finite extrema,
infinities, quiet/signaling NaN payloads and random full-bit inputs. Each of
the nine operands/parameters is varied individually; all parameter pairs
are also tested with infinities and NaNs. The checker compares all 44 state
bytes, ordered writes, every state data-read count, returned float bits, full
FPSCR and preserved r4-r11/d8-d15, SP and return PC. It separately requires
two reads of accumulator offset `0x1c`, covering the initial and post-clamp
loads. Mapped data accesses and stack canaries are guarded.

Read counts are compared, not full read ordering. This finite synchronous
model does not establish physical Cortex-M7 exception/timing behavior,
asynchronous publication safety, complete loop equivalence or firmware boot.
The report is `work/mainBoardGD-pi-model.json`, including content-based
provenance and a result digest. The [current plan](../PLAN.md) owns combined
integration totals; this isolated match does not claim whole-image equality.
