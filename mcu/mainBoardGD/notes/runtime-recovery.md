# Architectural runtime and storage recovery

Stock: mainBoardGD MD5 `fb64911bac422a27d7ed7fab3597603f`.
The common ATfE configuration now includes globally tested two-byte function
alignment (`-mllvm -align-all-functions=1`). This is partial source recovery,
not a complete runtime, boot test or binary-identical firmware build.

## Architectural assembly

`recovered/startup_runtime.S` uses architectural instructions, symbolic calls
and typed address pools. It does not embed stock opcode arrays or translate
ordinary C bodies into assembly to improve their score. The separate gate
`python3 tools/check-gd-runtime.py` compares six complete sections; the separate
`check-gd-scatter-handlers.py` adds two proven assembly-origin region handlers:

| Section | Execution address | Exact bytes |
|---|---:|---:|
| Runtime entry and continuation/address pool | `0x080003a4` | 20 |
| Reset, retained weak traps, default trap and shared pool | `0x080003b8` | 60 |
| Integer setjmp context | `0x08000488` | 26 |
| Integer longjmp context | `0x080004a2` | 36 |
| Scatter dispatcher and table-pointer pool | `0x080004c8` | 36 |
| Active exception unwind | `0x00000b10` | 30 |
| Scatter word copy | `0x0800335a` | 14 |
| Scatter word zero | `0x0800336a` | 14 |

These 236 bytes are runtime assembly, **not eight recovered C functions**.
The composite reset section includes nine retained weak trap loops and the
live default handler at `0x080003e4`. Reset clears the first 32 KiB of RAM with
STRD, calls SystemInit, then enters the runtime. Runtime entry loads SP from
the symbolic `0x2400b340` layout boundary. Scatter dispatch uses its original
non-C entry/continuation convention. The decompressor is C-origin and still
oversized, but now has the correct entry. The library's ELF `STT_FILE` identifies copy/zero as
`handlers.s`; their symbolic assembly now fits exactly. Their C versions remain
tested semantic references, explicitly excluded from active coverage rather
than counted as conflicting implementations. The already exact C null entry
stays the active implementation of its two bytes.

`clear_active_irq` follows the architectural inline assembly in Klipper's
`generic/armcm_irq.c`: test IPSR, construct a basic exception frame with its
Thumb-state bit and continuation PC, then use EXC_RETURN `0xfffffff9` to clear
active-handler state and resume in thread mode. The 30-byte full span is exact;
this byte gate does not test nested exceptions or physical Cortex-M7 unstacking.

Setjmp's selected integer path stores r8–r11/LR, r4–r7, SP and an FP-area
cursor in 44 bytes. The ABI reserves 160 bytes: local
`work/ac6/AC616/include/setjmp.h:57` declares `__int64 jmp_buf[20]`, and that
size fits the observed `0x240089f8..0x24008a98` interval. The selected stock
floating-point callback sites contain NOP.W. Reconstruction preserves those
NOPs and does not silently add FP-register saving/restoration. Longjmp maps
a requested zero return to one. Library-family evidence is not proof of the
original compiler version.

## Real zero-initialized objects

`runtime_state.c/.h` defines 49 actual objects at proven addresses. The gate
checks symbol sizes, alignment and SHT_NOBITS sections. These cover 23,675
of the scatter zero region's 33,976 bytes, including the 20,480-byte allocator
heap, serial buffers, motor acquisition/PWM state and 160-byte jump buffer.
The analog and button task wake bytes at `0x24003814/15` now have definitions.
JScope's 1,024-byte buffer at `0x24002e8c`, RTT's typed 168-byte control block
at `0x24003298`, and its 16/1,024-byte down/up buffers at `0x24003340/3350`
are separately proven by initialization sizes and descriptor setup.
One newly referenced ADC sample-cache base (`0x24008b18`) remains an incomplete
external array: its complete extent/overlap with inhibit bytes is not proven.

The remaining 10,301 bytes stay unclassified. No blanket zero arrays or
guessed stack objects fill the gaps. Zero-storage coverage is separate from
executable and initialized-flash coverage. The already exact 11,912-byte
initialized region and 3,284-byte scatter/load-data artifact are unchanged.

## C board entry and MPU API

`board_main.c` reconstructs ITCM `0x38b0..0x39da` (298 bytes). It calls vendor
MPU defaults/configuration/region-enable helpers, disables/enables MPU with
barriers and MemManage fault control, initializes two region descriptions,
enables I-cache/D-cache using CMSIS set/way loops, then calls JScope setup and
the scheduler. The stock return path remains present at the scheduler call
boundary. This translation compiles to 298 bytes; store grouping, scheduling
and cache-loop induction differ. Native Arm barrier intrinsics improve the
candidate from 227 to 245/298 bytes, preserving all 72 modeled
MMIO/barrier cases. The same interface makes `gd_system_reset` fully exact over
36 bytes; the prior local CMSIS GCC-style inline assembly scheduled differently.

`mpu.h` pins the 16-byte ABI: base word at offset 0, nine byte fields at 4–12,
and three untouched padding bytes. Defaults do not clear the whole structure.
Configuration writes RNR, RBAR, RASR in that order without extra field masks.
The complete helper extents are 78 bytes at `0x08001f88`, 18 bytes at
`0x08001fd8`, and 26 bytes at `0x08001ff0`; following alignment is not included.
Only region-enable is byte-exact. The candidate sizes are 76, 18 and 26 bytes.

`python3 tools/check-gd-board-mmio.py` verifies 72 modeled cases against stock:
three register/stack seeds, all four I-cache/D-cache enable combinations, and
six CCSIDR set/way encodings. Actual linked MPU helpers and their three bridges
execute. Interleaved MMIO accesses, barrier instructions, final register state
and handoff order match. Only JScope initialization and scheduler calls are
mocked. The tool pins source/header, partial-report, ELF and compared section
hashes; it does not simulate MPU permission checks, cache contents or timing.

## Remaining integration limits

The [current plan](../PLAN.md) records the changing partial-link totals and
explicit missing code bindings. Five complete source bodies remain
standalone-only: `__aeabi_memmove` 78/64 bytes, `__aeabi_memset` 18/14,
`__aeabi_memclr` 6/4, `memchr` 22/20 and C decompressor 128/94. All five now
have the correct symbol entry. Calibration is 68/68 bytes exact; timer OC
shadow/slave, the stepper loader, DQ limiter, GPIO reset/toggle, sine/cosine
and the C memset wrapper fit without truncation or movement.
Runtime assembly and typed ZI remain separate
from recovered C and initialized-data coverage.
No truncation, movement or padding conceals a slot/alignment
failure. MPU/cache execution models, where run, do not validate external
JScope/scheduler callees or establish real hardware operation.

Six memory/runtime routines now have C source in `runtime_memory.c`.
Copy/move at `0x080003f4` has void-return AEABI semantics, not standard C's
returned destination pointer; its two veneers share the same body. Native
tests cover overlap directions/alignment, zero counts, byte truncation and
unsigned string comparison. None is byte-exact. The global alignment option
corrects their former symbol shifts and admits `memset` at `0x08000446`:
18 bytes with 14 matching, in addition to the already integrated strcmp.
It preserves every byte in all 539 preceding partial-link sections, including
175 previously exact C bodies; it is not a per-function alignment override.

Microlib ELF metadata identifies memory helpers and decompression as C-origin,
with two-byte code alignment and `Prefer Size` optimization attributes.
They are not assembly-origin merely because they use compact instructions.
Their current C versions remain the source-recovery candidates, not copied
library instructions. The original `memseta.o` groups its set/clear/wrapper
bodies and uses `R_ARM_THM_JUMP11` for the clear tail call. A bounded experiment
with the same grouping under current flags instead inlined memset and enlarged
memclr; that experiment was rejected.

## Floating-point architectural compatibility

The square-root helper at `0x08002df8` now matches all 28 bytes, including its
zero literal. The former elementwise builtin speculated VSQRT before the C
positivity test and could add FPSCR.IOC for negative inputs. That gap is closed
with `arm_math_intrinsics.h`, a narrow compatibility shim for the original
SDK's volatile, read/write-register VSQRT interface. It contains no application
control flow, fixed register or opcode payload; the conditional and returns
remain C. The original application-level SDK spelling is still an inference.

The helper's separate model passes 16,672 output/FPSCR/ABI cases. The DQ
limiter model still explicitly executes stock sqrt, now independently matched
by the reconstructed helper. Sine/cosine fits at 452/480 bytes, but is not
byte-exact: 34,816 finite modeled cases compare output bits, sine-then-cosine
write order, FPSCR and ABI, including aliased outputs. Eight special-input
cases check bounded nonreturn without proving infinite execution or NaN-payload
propagation. Standalone sine, independent-operation timing and physical FPU
behavior are not validated by that model. [Compiler/alignment recovery](compiler-alignment-recovery.md)
records the SDK header provenance, globally tested option and remaining limits.
