# Reconstructed mainBoardGD generated layer

`generated.c` contains typed parser and response encoder records, parameter
arrays, shared strings, and the original compressed identify dictionary.
`lookup-match.c` contains the two C string lookup functions. These are separate
translation units of the same reconstructed layer, with no duplicate function
bodies. All values and lookup ordering are extracted from stock. The
shipped omission of `param_value` is preserved; unknown encoder strings return
NULL, and unknown static strings return 255.

`runners.c` supplies the three generated call-list functions from the actual
stock branch sequence. With the retained global configuration they reproduce
114/114 code bytes: init 26 bytes at 0x27c8, shutdown 38 bytes at 0x27e8, and
task 50 bytes at 0x2810. No runner has a literal pool. Following alignment gaps
(6, 2 and 6 bytes respectively) are not included in their function gates.

The source .ctr and generated calls disagree here too: watchdog_init and
watchdog_reset are declared but are absent from the shipped runners. The init
runner calls alloc_init, initial_pins_setup, timer_cnt_init, mclib_init (the
Klipper wrapper at 0x3d00), then serial_init. The task runner polls before and
after trsync_task, analog_in_task, buttons_task, timer_task, and console_task.
The shutdown runner's order is sendf_shutdown, move_reset, digital_out_shutdown,
stepper_shutdown, trsync_shutdown, analog_in_shutdown, clear_active_irq, timer_reset.
These sequences are validated against the actual Thumb branches on every emission.

Regenerate from the repository root:

```sh
python3 tools/emit-gd-generated.py
python3 tools/emit-gd-generated.py --check --verify
```

The second command compiles the C for ARM32 with the available GCC toolchain,
links its data at measured addresses, and compares every emitted data byte to
stock. The manifest records every checked range. Handler pointers resolve to
their stock addresses solely for this check; their bodies are separate work.

`verify-data.ld` is a data validation harness, not the firmware linker script.
For this check only, GD_VERIFY_DATA_ONLY materializes the eleven strings that
the real lookup compilation places in code-adjacent literal pools. The macro
is absent from the actual combined build. The stock compiler remains unpinned.
No executable machine-code arrays or binary includes are used.

`lookup-match.c` also supports an isolated executable lookup gate. Its local
string literals are expressed naturally; shared strings and
encoder records are external symbols resolved to their observed addresses by
`verify-lookups.ld`. The stock strcmp call goes through the ITCM veneer at
0x5b8a. `--verify-combined` builds both actual C translation units and links
their shared string and encoder symbols together using `verify-combined.ld`.
Only external handler bodies and the strcmp veneer remain address-only inputs.

ATfE 22.1.0 can run the same data check with `--compiler /path/to/clang`.
Its baseline `-O2 -mcpu=cortex-m7 -mfpu=fpv5-d16 -mfloat-abi=hard` emits
movw/movt for local strings. The explicit candidate GLOBAL setting
`--promote-constants` adds `-mllvm -arm-promote-constant`, reproducing stock's
ADR and literal-pool policy in both lookup functions. This is compiler
configuration evidence, not proof of the original compiler version.

```sh
python3 tools/emit-gd-generated.py --check --verify --verify-lookups \
    --compiler work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang --promote-constants \
    --cflag=-fno-unroll-loops --cflag=-falign-loops=4
```

Measured with ATfE 22.1.0: generated data remains 4,536/4,536 bytes exact in
102 sections. `ctr_lookup_encoder` is 640/640 bytes exact at 0x21a0: all
496 code bytes (160 instructions) and 144 literal-pool bytes. The static
lookup is still 862/932 bytes equal: 722/792 code bytes (218/284 instructions)
and all 140 pool bytes. Its return value uses r0 where stock uses r1. The
static pool ends at 0x27c4; following alignment before 0x27c8 is not claimed.
The combined lookup gate deliberately exits nonzero while this mismatch remains.

The register mismatch is explained by SelectionDAG scheduling: ATfE places the
final strcmp comparison before loading the default result (-1), permitting r0
to hold both. Stock loads the result in r1 before comparing r0, extending the
overlap and forcing r1 for the shared result in every return block.

Diagnostic `--cflag=-mllvm --cflag=-pre-RA-sched=list-burr` reproduces both
lookup functions exactly: 1,572/1,572 bytes including both literal pools and
444/444 instructions. With this diagnostic, `--verify-combined` verifies
5,956/5,956 unique bytes across the integrated data, lookup code and runners. Local
literal bytes are counted only once. All four original probes remain exact.
However, cross-module validation rejects adopting this scheduler globally:
SystemInit falls from 543/548 to 517/548 matching bytes, and the motor subset
falls from 10/13 exact functions (500 bytes) to 6/13 (282 bytes). No per-function
scheduler override has been added. This is diagnostic evidence, not a globally
valid recovery result. The normal global configuration still has the 70-byte
static-lookup difference.

Other global scheduler diagnostics: list-hybrid/list-ilp also match both lookups
but regress the original set_hold_current probe; fast/linearize grow the encoder
four bytes. Disabling machine scheduling, source/top-down/bottom-up scheduling,
register-pressure/live-use/vrcycle priorities, and two-address rescheduling does
not close the static mismatch. Disabling physical-register joining additionally
regresses the encoder. None of these alternatives is a default.

Three equivalent C spellings (shared exit/result variable, signed result with
else chain, signed-byte unknown return) produced the same static mismatch;
none was retained. All four original ATfE probes (timer_is_before,
timer_read_time, set_hold_current, set_run_current) remained exact, 126/126
bytes, when rebuilt with this same candidate global constant-promotion setting.

The canonical machine-readable verification report is generated with:

```sh
python3 tools/emit-gd-generated.py --check --verify --verify-lookups \
    --verify-runners --verify-combined \
    --compiler work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang --promote-constants \
    --cflag=-fno-unroll-loops --cflag=-falign-loops=4 \
    --report work/mainBoardGD-generated-verification.json
```

All requested gates execute even when a lookup or combined check fails. The
report records explicit failing intervals, separate exact literal-pool ranges,
source and expected/candidate byte hashes, and the complete compiler invocation.
Its overlapping data/pool intervals must be deduplicated when totaling progress.
Reports produced with rejected diagnostic compiler options must use a separate
filename and must not replace the canonical retained-configuration result.
