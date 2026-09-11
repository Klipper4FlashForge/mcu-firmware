# Runtime translation-unit and call-boundary experiment

Measured 2026-09-09 with retained ATfE 22.1.0 and the shared mainBoardGD
flags, including two-byte function alignment. No canonical C, flags or
linker inputs changed.

The legacy microlib `memseta.o` contains the AEABI set helper, clear wrapper
and C `memset` wrapper together. Stock's clear wrapper is four bytes at
`0x08000442`: set r2 to zero, then a short branch to `0x08000434`.
Our separately compiled C clear wrapper is six bytes: the same argument
setup followed by a wide branch. This makes translation-unit grouping an
evidence-based hypothesis, independent of the set helper's other mismatch.

## Measurements

Scratch sources and compiler products are in
`/tmp/gd-runtime-group.w9P0WH/`; temporary storage is not a durable artifact.
Each source implements the same byte-fill loop and ordinary AEABI/C wrappers.
No emitted assembly was edited.

| Source arrangement | Set body | Clear body | C wrapper | Observation |
|---|---:|---:|---:|---|
| One translation unit, ordinary definitions | 18 | 22 | 18 | Compiler inlines the fill loop into both wrappers |
| Same unit, set helper `noinline` | 18 | 6 | 18 | Observed calls survive, but clear still uses `R_ARM_THM_JUMP24` |
| Same call boundary and one shared `.text.memseta` section | 18 | 6 | 18 | Grouping does not select a short branch |
| Local helper with exported AEABI alias, shared section | 18 | 6 | 18 | LLVM canonicalizes calls back to the exported helper; same wide relocation |

These are compiler symbol extents, not stock-address byte-match scores.
Stock extents are 14, 4 and 18 bytes respectively. A wrapper with matching
length is not necessarily byte-identical; the C wrapper's argument shuffle
still differs. The grouping proposals therefore are not adopted.

The shared-section proposal was also compiled to textual assembly and
assembled unchanged by GNU Arm assembler 10.3. Its stock-compatible ISA/ABI
settings were Cortex-M7, FPv5-D16 and hard float. The first invocation rejected
LLVM's `.addrsig` metadata directive. Re-emitting with `-fno-addrsig` allowed
the diagnostic without editing any generated instructions. GNU assembler
also emitted the wide `R_ARM_THM_JUMP24` relocation; changing assembler did
not solve the call width. It additionally rounded the shared section with
two bytes of padding after the final function.

## Consequence

Simply combining these three C functions is insufficient with this compiler.
The four-byte clear wrapper remains a standalone exclusion, alongside the
other documented oversized runtime bodies. No short branch is manufactured
through assembly, opcode replacement, or relocation rewriting. These finite
experiments do not prove that no legal C/toolchain arrangement can match;
they close the straightforward grouping hypothesis proposed in
[runtime compiler provenance](runtime-compiler-provenance.md).
