# mainBoardGD — recovery in progress

The active recovery target is the GD32H757 main board. Its stock layout
and generated command layer are extractable; a reconstructed firmware
build does not exist yet. The exact compiler version, GD32H7 port and
motor-control implementation remain open.

| | |
|---|---|
| MCU / reported clock | `gd32h757zg`, 600 MHz |
| load address | `0x08000000` |
| stock image | `stock/mainBoardGD.bin`, 45,552 B, MD5 `fb64911bac422a27d7ed7fab3597603f` |
| commands | 49 |
| dictionary stamp | `?-20260529_142047-ubuntu`, `build_versions` GCC 7.3.1 / binutils 2.34 |
| executable toolchain | ARM scatter-loading runtime and microlib; code generation strongly indicates armclang |
| working probe compiler | open ATfE 22.1.0: four isolated functions, 126/126 bytes exact, including literal pools |
| working upstream baseline | `6d70050`, compatible with recovered declarations; exact source vintage is not established |

The executable differs from the dictionary's build stamp: ARM's linker
places startup/runtime and motor code in flash, copies 28,120 bytes of
code and rodata to ITCM at address zero, expands 11,912 bytes of data into
RAM, and clears a further 33,976 bytes. Microlib matches identify the
runtime, but cannot distinguish the candidate compiler releases.

The surviving `.compile_time_request` text describes sources that differ
from the generated command tables beside them. Preserve both artifacts:
the declarations include `param_value`, but the encoder lookup returns
null for that message. Regenerating tables from these declarations alone
would change stock behavior. All 49 command handlers are named.

The 2026-09-09 work adds reproducible layout and generated-layer
extraction, an assembly-checked startup map, and an address-cited motor
control account. The vector table has 233 slots including SP; 86 branch
veneers connect flash and ITCM. Ghidra's startup output loses repeated
MMIO reads and overstates the init runner's boundary, so it needs assembly
checks before translation into C.

[PLAN.md](PLAN.md) records the next work and build gates.
[Startup and layout](notes/startup-layout.md),
[motor control](notes/motor-control.md), and
[handler addresses](notes/handlers.md) carry the implementation evidence.
[The initial reconnaissance](notes/recon.md) supplies the earlier analysis.

Open ATfE 22.1.0 now reproduces two timer helpers and both motor-current
setters exactly: four isolated functions, 126/126 bytes including literal
pools. Run `python3 tools/check-gd-toolchain.py --cc /path/to/clang`
to compile the retained source probes and write a JSON comparison.
`-O2 -mcpu=cortex-m7 -mfpu=fpv5-d16 -mfloat-abi=hard` passes these probes;
this does not identify stock's compiler or establish whole-firmware flags.
The older local armclang 6.16 still requires its licence, but no longer
blocks these source-matching experiments.

[Recovered C](recovered/README.md) now matches twenty-three motor functions,
nineteen core/FlashForge functions, twenty serial functions, forty-one base/scheduler
functions, four GPIO helpers, three generated
runners, the 640-byte encoder lookup, the 28-byte vector-table helper and
4,536 bytes of generated data. These are overlapping isolated gates, not
whole-image coverage. `SystemInit` has two differing bytes; its MMIO traces
match in four modeled scenarios. Static lookup and several source bodies
remain open. A partial integration ELF now has 187 exact C functions out of 281
(11,006 complete-span bytes; 94 mismatches), passes all 456 isolated-parity checks, and preserves
all 11,912 initialized RAM bytes, plus exact symbolic vectors and veneers. It is
reproducible but not bootable: complete source/runtime and image layout remain.
The source-only scatter encoder now reproduces all 3,225 compressed bytes;
rebuilt scatter records and alignment extend that exact flash span to 3,284
bytes. Scheduler startup and timer insertion are exact. Protocol framing and
motor PWM bodies are reconstructed but still have code-generation mismatches.
Six stepper functions are exact; its loader now fits the observed 96-byte slot.
[Stepper pin-width recovery](notes/stepper-pin-width-recovery.md) corrects two
caller-side byte truncations: config remains nonexact at 31/106 matching bytes
in a 104-byte candidate. Its 7,210 modeled cases and 13 self-tests pass; run
`python3 tools/check-gd-stepper-config-model.py` after the stepper byte gate.
[Generated lookup permutation](notes/generated-lookup-permutation.md) records
the strict 20,000-iteration search of the static lookup's remaining 70 code
bytes; no improving or semantically valid candidate was found.
Runtime assembly, including proven assembly-origin scatter handlers, matches
another 236 bytes, separately from C recovery. Typed zero-storage now covers 49 objects,
including JScope/RTT buffers, leaving 10,301 zero-region bytes unclassified.
The newly recovered ADC sample-cache base still has an unproven extent.
Both complete motor loops and
the board MPU/cache path are in C but still non-exact. Trigger-sync adds ten
exact functions; GPIO-output source passes 10,156 modeled ABI/MMIO cases but
does not yet match instruction bytes. Motor IRQs and two endstop handlers now
match exactly; SysTick, ADC/DMA helpers, motor arithmetic and the full hardware
initializer are reconstructed but not all exact. ADC SDK recovery adds eleven
exact functions and digital output adds three; the angle table and protocol
constants now have exact typed definitions. Analog/buttons add nine exact
functions, timer/DMA/control seven, PWM/current seven, JScope one, and the last
actual fault trap another. Sine, timer and RTT constants add 629 exact data bytes.
The link retains four explicit missing code targets and excludes five
oversized standalone bodies; their entry addresses are now correct. The two C versions of assembly-origin
scatter handlers remain tested semantic references, not active coverage.
Calibration and system reset are now exact; both formerly oversized timer
functions, the loader, DQ limiter, GPIO reset/toggle, sine/cosine and C memset
wrapper now fit. A globally tested two-byte function-alignment option preserves
all 539 preceding partial-link sections. The square-root helper is independently
exact over 28 bytes using the original SDK's narrow VSQRT architectural
interface, with 16,672 modeled cases. The DQ model still uses the identified
stock callee; sine/cosine separately passes 34,824 bounded model cases. These
models do not prove physical FP timing or standalone sine equivalence.
See [compiler/alignment recovery](notes/compiler-alignment-recovery.md) and the
[peripheral/input record](notes/peripheral-input-recovery.md) for this batch.
The [slot-recovery record](notes/slot-recovery.md) explains the subsequent fixes,
and the [gap audit](notes/remaining-code-map.md) classifies all apparent code gaps.
[Motor publication recovery](notes/motor-publication-recovery.md) adds exact
GPIO disable and a closer reset body whose 1,040 modeled cases execute actual
stock callees. Reset uses two documented alignment bytes and remains unmatched.
The same record adds four newly exact trigger-sync bodies from callback-record
publication order and seven-byte field clearing that leaves padding untouched.
[Runtime compiler provenance](notes/runtime-compiler-provenance.md) records
legacy library metadata without claiming the unproven original producer.
[Atan permutation searches](notes/atan-permutation-search.md) retain both
20,000-iteration runs and the semantic rejection of a closer candidate; atan
remains 599/640 matching bytes.
[PI reload recovery](notes/pi-reload-recovery.md) adds the complete 116-byte
PI update, exact with 56,096 modeled cases and unchanged global flags.
[ADC source shaping](notes/adc-source-shaping.md) adds exact trigger and
special-function helpers, bringing ADC to 11/16 exact functions and 826 bytes.
[PWM update](notes/pwm-update-recovery.md) improves to 95/228 matching bytes
at the complete 228-byte extent and passes 32,256 modeled cases;
[PWM initialization](notes/pwm-source-shaping.md) improves two still-unmatched
bodies while preserving seven exact helpers. [Protocol/console trials](notes/protocol-crc-shapes.md)
record rejected shapes without source changes.
[Queue/button publication](notes/queue-buttons-publication.md) adds exact
40-byte queue insertion and a closer button-query body.
[Motor step](notes/motor-step-recovery.md) improves to 150/156 matching bytes
at the correct extent, with 32,256 ordered-access/FP/ABI model cases passing.
[Loop-B access recovery](notes/loop-b-access-recovery.md) restores ordered
state accesses and both directional FP subtractions. Its complete 860-byte
candidate matches 104 bytes and passes 37,888 caller-model cases plus 19
self-tests; external motor callees are mocked, and the body remains nonexact.
[ADC/digital follow-up](notes/adc-digital-followup.md) adds a closer deinit body
and rejects a semantically wrong digital candidate; [trigger shaping](notes/trsync-trigger-shaping.md)
records a completed search with no source change.
[Statistics reload recovery](notes/statistics-reload-recovery.md) adds a
complete 232-byte match and 1,564 modeled cases. [Move-reset shaping](notes/move-reset-shaping.md)
improves the still-nonexact reset to 66/86 matching bytes at its correct extent.
[Shutdown call contract](notes/shutdown-call-contract.md) adds a complete
20-byte try-shutdown match and 3,614 actual nonlocal-jump model cases.
[Queue/OID shaping](notes/queue-oid-shaping.md) retains two completed searches
without a source change.
[Runtime memory shaping](notes/runtime-memory-shaping.md) records the audited
runtime search without adopting a candidate.
[ADC setup shaping](notes/adc-setup-shaping.md) closes three hand trials and
20,000 search attempts without improving the 219/220-byte baseline.
[Button ACK shaping](notes/buttons-ack-shaping.md) records a completed search
without improving its 98/104-byte baseline.
[ADC cache layout](notes/adc-cache-layout.md) records the real channel-18 store
without assuming an array extent. Rejected [runtime grouping](notes/runtime-call-boundary.md),
[static-lookup shapes](notes/generated-lookup-shape.md), and
[CPU tuning](notes/cpu-tuning-diagnostics.md) experiments remain diagnostics.
Run `python3 tools/check-gd-recovery.py` for the combined regression checks.
The last full wrapper, at the shutdown/loop-B checkpoint, passes 38/70 gates; the remaining 32 failures are documented
byte mismatches, not stale reports or model failures. All 45 inventory reports
are fresh and conflict-free, with 28,638 unique exact runtime bytes excluding
zero-initialized storage. The separately validated pin-width correction changes
only nonexact `command_config_stepper` against `/tmp/gd-shutdown-loop-final-repeat`,
with all 187 exact C functions and every other exact section preserved.
Its partial build in `/tmp/gd-stepper-validation.WLzpFb/partial` passes 456/456
parity checks and preserves all initialized RAM; exact totals stay unchanged.
At the preceding checkpoint, all 186 prior exact C functions and every other
exact section remained unchanged; only try-shutdown and nonexact loop B changed against
`/tmp/gd-baseline-186.json`. An independent build in
`/tmp/gd-shutdown-loop-final-repeat` reproduced that checkpoint's canonical ELF and RAM.
The preceding shutdown-only checkpoint reproduced in `/tmp/gd-shutdown-final-repeat`.
The historical statistics/reset checkpoint (`/tmp/gd-stats-reset-final-repeat`)
preserved all 185 prior exact C functions while changing only statistics update
and move reset. The historical queue/step
checkpoint preserved all 184 ADC/PWM matches; that checkpoint preserved all
182 PI matches, and PI preserved its preceding 181 matches. No whole-image
equality or flashable build is claimed.
