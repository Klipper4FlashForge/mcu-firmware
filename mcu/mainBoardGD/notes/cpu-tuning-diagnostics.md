# Global CPU-tuning diagnostics

No tuning option was adopted. All six diagnostic builds produced a
**byte-identical complete partial ELF** to the frozen baseline: no exact
function regressions, no gains, and no changed measured sections.

The baseline reproduces the 181/281 exact C-function checkpoint,
10,460 exact C bytes, plus the existing exact data/runtime sections.
This is still a partial ELF, not whole-image equality.

## Scope and results

Retained notes contained an earlier `-mcpu=cortex-m3` runtime experiment,
but no corresponding `-mtune` sweep. That ISA-changing experiment was
not repeated. These builds retain `-mcpu=cortex-m7`, `fpv5-d16`, hard-float
ABI and every existing common flag, appending tuning options **globally
to every compiled C unit**:

| Additional global options | Exact C functions | Regressions / gains | Full partial ELF |
|---|---:|---:|---|
| `-mtune=cortex-m3` | 181/281 | 0 / 0 | Identical |
| `-mtune=cortex-m4` | 181/281 | 0 / 0 | Identical |
| `-mtune=cortex-m33` | 181/281 | 0 / 0 | Identical |
| `-Xclang -tune-cpu -Xclang cortex-m3` | 181/281 | 0 / 0 | Identical |
| `-Xclang -tune-cpu -Xclang cortex-m4` | 181/281 | 0 / 0 | Identical |
| `-Xclang -tune-cpu -Xclang cortex-m33` | 181/281 | 0 / 0 | Identical |

ATfE 22.1.0's `-###` output does not forward the ordinary `-mtune`
arguments to cc1 for this ARM target. The explicit cc1 diagnostic does
reach optimized LLVM IR: a probe has `"target-cpu"="cortex-m7"` alongside
`"tune-cpu"="cortex-m4"`, with unchanged target features. Nevertheless,
none of the three explicit tuning values changes the resulting corpus.
This is evidence that these options offer no useful code-generation
lever here, not proof about all ARM compiler scheduling implementations.
In particular the static lookup remains 862/932 bytes matching.

## Frozen inputs and comparison

Before building, tools and the entire board directory were copied into
`/tmp/gd-tune-global.R4v0rx/root/`. Compiler and Klipper/CMSIS paths were
shared read-only through symlinks. Transitive source/header hashes were
checked after all runs, as were compiler, stock and linked ELF hashes.
Report source maps agree after normalizing only the build-output paths
of generated `vectors.c` and `linker-bridges.S`; their content hashes
also agree. This isolates concurrent edits to canonical recovered C.

The comparison checks all 543 report rows by kind, name and absolute address,
including complete candidate size, bytes hash, matching-byte count and
exact status. It additionally compares the complete linked ELF hash,
so unchanged scores alone are not the reason for rejection.

Full partial ELF SHA-256, identical in all seven builds:
`c0119bda6c02d9c2e86090d938cc5168c75aadfafdfd966c2b9be9b410064ae9`.
Frozen baseline report SHA-256:
`db6048c26276b7782dbad4325a6219602d3bbe0ee3ba79cc583ebf6ffc3985a5`.

Scratch records include the frozen tree, all seven builds and their
`results.json`/ELF files, `compare.py`, `comparison.json`, driver command
traces, and `tuned-probe.ll`. `/tmp` artifacts are temporary and are not
part of the durable build deliverable. No canonical C, compiler flags,
profile tooling or scoreboards were changed by this experiment.
