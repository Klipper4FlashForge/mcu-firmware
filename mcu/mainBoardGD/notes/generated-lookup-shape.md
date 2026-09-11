# Generated static lookup: bounded source-shape follow-up

No source or compiler setting was adopted. Under the current common ATfE
22.1.0 configuration, `ctr_lookup_encoder` remains 640/640 bytes exact.
`ctr_lookup_static_string` remains 862/932 matching: 722/792 code bytes
and all 140 literal-pool bytes, at its actual `0x2420` entry. The 70-byte
difference is distributed register-selection differences, not a 70-byte
function extent. The pool ends at `0x27c4`.

The earlier rejected experiments in `recovered/generated/README.md` were
reviewed first. In particular, `list-burr`, `list-hybrid`, `list-ilp`,
machine-scheduler controls, shared-exit and signed-result variants were
not rerun. Their lookup-only successes do not justify global settings
that regress other functions.

Three additional scratch-only C spellings were compiled and linked with
the **unchanged canonical compiler command** from
`work/mainBoardGD-generated-verification.json`:

| Source hypothesis | Encoder | Static lookup | Result |
|---|---:|---:|---|
| Ordinary correctly prototyped `strcmp` instead of explicit builtin | 640/640 | 862/932 | Both sections byte-identical to baseline |
| Start ID at 2 and increment after each unsuccessful comparison | 640/640 | 862/932 | Both sections byte-identical to baseline |
| `switch (strcmp(...))`, case zero returns ID, default continues | 640/640 | 862/932 | Both sections byte-identical to baseline |

All candidates retain the exact function extents and literal pools.
The counter and switch spellings optimize to the same LLVM IR as the
baseline, apart from source-file identification. The ordinary-call
diagnostic changes declaration/call attribute bookkeeping but not the
emitted code. The local Klipper generator itself uses
`__builtin_strcmp`; the ordinary-call variant is therefore a diagnostic,
not evidence that the recovered spelling should change.

The final optimized IR still contains:

```llvm
%95 = tail call i32 @strcmp(...)
%96 = icmp eq i32 %95, 0
%97 = select i1 %96, i8 33, i8 -1
```

That value joins the shared `i8` result phi. These spelling changes do
not prevent the final comparison/default result from reaching the same
SelectionDAG shape. The previously observed stock-versus-candidate
difference in scheduling the default result before/after the comparison
therefore remains unresolved. This rules out these particular source
spellings, not every source-level solution or backend hypothesis.

Scratch source, `.ll`, object and linked ELF files, a complete-span
checker, and JSON result records are retained in
`/tmp/gd-static-shape.Y9N7Gk/`. No bytes are aligned or normalized in its
comparison. Both pool ranges are explicitly checked. Temporary artifacts
are not a durable build deliverable.

Baseline source SHA-256:
`ac141f99339f441e13ab8995577b64f6160961e3da6f7bbe31570e3b1e4bde10`.
Static-section SHA-256, identical for all four builds:
`aa8e05fae8416f92df79c004080add0861119772def0561486085ba3ab7cb3a9`.
Encoder-section SHA-256, identical for all four builds:
`30f893069dbc4ce870835d1ffc70556d35d2dd21af195e960f9caf8816dff005`.

There is no improved candidate to promote to a whole-corpus gate, and no
new global-option compatibility claim. Canonical generated C, emitter,
flags and scoreboards remain unchanged.
