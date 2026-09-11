# Runtime compiler provenance

Local audit on 2026-09-09. Five complete microlib ELF members are identical
across three locally retained library packages. This includes their debug and
attribute sections, not only instructions. Their metadata supports legacy
ARMCC-format runtime provenance, but does not identify an exact compiler
producer version or date the mainBoardGD application build.

The packages are:

| Local archive | Its `version.o` string |
|---|---|
| `work/ac6/AC616/lib/armlib/mc_w.l` | `ARM C Library, ARM Compiler 6.16` |
| `work/mdk/opt/wine_keil/drive_c/Keil_v5/ARM/ARMCC/lib/armlib/mc_w.l` | `ARM C Library, RVCT5.06 [Build 34]` |
| `work/mdk/opt/wine_keil/drive_c/Keil_v5/ARM/ARMCLANG/lib/armlib/mc_w.l` | `ARM C Library, ARM Compiler 6.7` |

These are library-package labels from `version.o`, not producer strings in
the five matching members. The three `version.o` objects differ. None of the
three version strings occurs in the stock firmware. AC6.16's local
`sw/manifest.txt` also names that installed package and its tools; it does not
date the retained code inside its libraries.

| Member | Whole ELF bytes | SHA256, identical in all three archives |
|---|---:|---|
| `__dclz77c.o` | 1,200 | `9f65afb90dbbb22e39dd4bf7157bf1e117ec3ddbae0168708d0cfb5ec8b6abde` |
| `memmovea.o` | 1,320 | `ca4b96d594203589275ff1a92ba945f9c4fcf4382fe5c9968ab4ad05b013547f` |
| `memseta.o` | 1,428 | `8e3556b6ff2459fd570e5eae161ff5ff66c52cd075ca3c14512e1e2d36c9c6a3` |
| `strcmp.o` | 1,096 | `f4168dcec158239fb509d4c4d8b319df6beb5f0148013a3eecced8ff4639a00d` |
| `memchr.o` | 1,080 | `1419bf84032c5a5313906945ac4e4db0a090c0734ab3547cd36c1c952139802e` |

Their `.text` sizes are respectively 94, 64, 36, 28 and 20 bytes. The matching
stock spans are decompression at `0x080004ec`, the shared copy/move body at
`0x080003f4`, the set/clear/wrapper group at `0x08000434`, strcmp at
`0x08000458`, and memchr at `0x08000474`. The set/clear/wrapper group's actual
entries occupy 14, 4 and 18 bytes. Its relocations are part of the object-level
evidence; a relocatable object is not itself a complete linked firmware span.

## What the metadata establishes

All five members have a DWARF `.debug_frame` CIE with version 3 and literal
augmentation string `armcc+`. Each `.arm_vfe_header` consists of four zero
bytes. They carry the same Arm-private build attributes, including the
`BuildAttributes$$...$OSPACE$REQ8$PRES8$EABIv2` symbol. Together these are strong
evidence of retained legacy ARMCC-format objects, even in packages branded
Arm Compiler 6. They are not evidence that the application uses the same
compiler backend or options.

Their `.ARM.attributes` report CPU name `7-M`, Thumb-2, optimization goal
"Prefer Size", forced-int enums, and ABI conformance `2.09`. Their code-section
alignment is two bytes. No VFP-register calling-convention attribute is
present; this is not the application's Cortex-M7 hard-float profile. The
conformance value is an ABI revision, not a compiler version. The zero VFE
header supplies no additional version information.

None of the five objects has `.debug_info`, `.debug_str` or `.comment`; there
is no `DW_AT_producer` string to extract. The archive member timestamps differ:
the ARMCC package reports 2017-01-28, the ARMCLANG package 2017-03-17, and AC6.16
2021-03-03. Those are archive-container timestamps, not a reliable compiler
build date. Whole-object identity across those differently labeled packages
prevents choosing one of their versions as the unique original producer.

The local MDK `ARMCC` directory contains only `lib`; no `armcc` executable is
present there or available on PATH. AC6.16 contains armclang and associated
tools, but their installed version cannot identify the producer of these
unchanged runtime objects. Even `fromelf --vsn` currently fails its ordinary
license checkout. No environment/product switching or license workaround is
part of this audit.

## Rejected configuration diagnostics and useful next work

The retained temporary reports record bounded LLVM configuration experiments:

| Diagnostic output | Overrides to the shared configuration | Result |
|---|---|---|
| `/tmp/gd-runtime-oz/results.json` | `-Oz -falign-loops=2` | 0/6 memory functions exact |
| `/tmp/gd-runtime-os/results.json` | `-Os -falign-loops=2` | 0/6 memory functions exact |
| `/tmp/gd-runtime-m3-oz/results.json` | `-Oz -mcpu=cortex-m3 -falign-loops=2` | 0/6 memory functions exact |
| `/tmp/gd-scatter-oz/results.json` | `-Oz -falign-loops=2` | decompressor 108/94 bytes, unmatched; only the already-exact null helper matches |

The M3 diagnostic overrides the CPU but retains the shared FPU/ABI flags; it
is not a reconstruction of a complete legacy runtime build profile. Some
diagnostics make a body fit or match its length without matching its bytes.
None is adopted on that basis. These experiments leave the current shared
compiler configuration unchanged.

A useful additional toolchain experiment, if a legitimately working legacy
ARMCC compiler becomes available, is a consistent runtime-component build
starting with the small memchr/strcmp bodies. The locally identified RVCT
5.06 build 34 package is a concrete comparison baseline, not a proven producer.
Any separate runtime profile needs evidence for the whole component's target,
ABI and optimization policy; it must not become a set of per-function options
selected only for higher scores.

Source work remains worthwhile with the available compiler. In particular,
the shared `memseta.o` arrangement and its short clear-to-set relocation offer
a concrete C translation-unit/call-boundary hypothesis. The subsequent
[grouping experiment](runtime-call-boundary.md) finds that ordinary grouping,
preserved calls, a shared section and a local-helper alias still do not select
the short branch with ATfE; none is adopted. Complete C control
flow and ABI reconstruction remain the source deliverable. There is no basis
to replace these C-origin functions with assembly, or to assert that only a
legacy compiler could ever reproduce them. Relinking original library objects
would be a separately labeled binary dependency, not source recovery. Lack
of an available legacy compiler does not block application-source progress.

## Reproduce the local evidence without writing files

Run from the repository root with system `ar` and Python `pyelftools`. This
reads members through stdout, checks whole-object identity, prints their
metadata and tests package-string absence from stock:

```sh
python3 - <<'PY'
import hashlib, io, re, subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile

archives = [
    Path('work/ac6/AC616/lib/armlib/mc_w.l'),
    Path('work/mdk/opt/wine_keil/drive_c/Keil_v5/ARM/ARMCC/lib/armlib/mc_w.l'),
    Path('work/mdk/opt/wine_keil/drive_c/Keil_v5/ARM/ARMCLANG/lib/armlib/mc_w.l'),
]
def member(archive, name):
    return subprocess.check_output(['ar', 'p', str(archive), name])
stock = Path('mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
for archive in archives:
    blob = member(archive, 'version.o')
    label = re.search(rb'ARM C Library,[^\0]*', blob).group()
    print(archive, label.decode(), 'present in stock:', label in stock)
for name in ('__dclz77c.o', 'memmovea.o', 'memseta.o', 'strcmp.o', 'memchr.o'):
    blobs = [member(archive, name) for archive in archives]
    assert blobs[0] == blobs[1] == blobs[2], name
    print(name, len(blobs[0]), hashlib.sha256(blobs[0]).hexdigest())
    elf = ELFFile(io.BytesIO(blobs[0]))
    frame = elf.get_section_by_name('.debug_frame').data()
    print('CIE version:', frame[8], 'augmentation:', frame[9:].split(b'\0')[0])
    print('VFE:', elf.get_section_by_name('.arm_vfe_header').data().hex())
    print('text alignment:', elf.get_section_by_name('.text')['sh_addralign'])
    print('producer sections:', [s.name for s in elf.iter_sections()
          if s.name in ('.debug_info', '.debug_str', '.comment')])
    for subsection in elf.get_section_by_name('.ARM.attributes').iter_subsections():
        for scope in subsection.iter_subsubsections():
            for attribute in scope.iter_attributes():
                print(attribute)
PY
```

The package labels and code-library match are also recorded in
[reconnaissance](recon.md). [Fixed-slot recovery](slot-recovery.md) explains why
the separately proven `handlers.s` copy/zero assembly is a different provenance
case from these five C-origin objects.
