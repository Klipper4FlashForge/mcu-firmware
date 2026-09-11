# The tools

| | |
|---|---|
| `extract-dict.py` | pull the Klipper data dictionary out of a raw image |
| `scatterload.py` | decode ARM scatter records and expand mainBoardGD's ITCM/data regions |
| `extract-ctr.py` | recover surviving NUL-delimited `.compile_time_request` declarations from expanded RAM data |
| `extract-gd-layout.py` | extract mainBoardGD's vector table, scatter records and flash/ITCM branch veneers into JSON |
| `extract-gd-generated.py` | extract mainBoardGD parser/encoder records, `.ctr`, identify dictionary and static-string lookups, checking their consistency |
| `emit-gd-generated.py` | emit typed generated C, lookups and runners; compare isolated and combined generated sections against stock |
| `check-gd-recovery.py` | run all mainBoardGD isolated regression gates with one global configuration and record their results |
| `build-gd-partial.py` | link actual recovered units, symbolic vectors/veneers and typed data; audit explicit unrecovered dependencies (not flashable) |
| `check-gd-partial-parity.py` | compare every non-synthesized partial section against its fresh canonical isolated candidate; not stock equality |
| `report-gd-gaps.py` | classify inventory gaps using verified vector/veneer/scatter artifacts and explicit zero-alignment inferences |
| `check-gd-serial.py` | compare serial IRQ/init, buffering and USART vendor routines at stock addresses |
| `check-gd-base.py`, `gd_function_gate.py` | compile base/debug/OID and scheduler C profiles; compare full function and local-pool spans with source provenance |
| `check-gd-state.py` | verify typed motor/GPIO/timer initializers against scatter-expanded RAM |
| `gd_scatter_compress.py` | source-only scatter LZ77 encoder; generic lazy lexicographic 128-byte-key dictionary reproduces all 3,225 compressed bytes; synthetic self-tests |
| `build-gd-image.py` | paint the partial ELF and scatter span into a whole 45,552-byte candidate image and count differing bytes against stock, per section and per uncovered gap; the board's `cmp -l` gate |
| `sweep-gd-compilers.py` | rerun partial link (diagnostic overflow mode), scatter and image gates under several `label=clang` compilers and tabulate exact functions and matching bytes per release |
| `build-gd-scatter.py` | rebuild RAM from candidate ELF sections, compress it and emit semantic scatter records/alignment; exact 3,284-byte load-data span, not firmware |
| `check-gd-protocol.py` | full-function gates for command dispatch/framing, console transport, acknowledgements and CRC |
| `check-gd-stepper.py` | complete stepper code/pool spans, including the fitting but unmatched loader |
| `check-gd-trsync.py` | complete trigger-sync handlers, callbacks, signal dispatch and tasks |
| `check-gd-irqs.py` | motor sample IRQs, stock fault traps, SysTick dispatcher and timer task |
| `check-gd-adc-irqs.py`, `check-gd-dma-irqs.py` | complete peripheral interrupt flag/status code spans |
| `check-gd-peripheral-irqs-mmio.py` | execute linked ADC/DMA helpers against stock and an independent MMIO oracle; finite modeled behavior, not hardware validation |
| `check-gd-endstop.py` | complete endstop configuration, homing, query and oversampling spans |
| `check-gd-math.py` | motor inverse Park, voltage limiting, observer and square-root C gates |
| `check-gd-hardware.py` | complete motor hardware initializer and independent direct-call sequence audit |
| `check-gd-adc-vendor.py` | 16 ADC SDK register/channel bodies, with native `--self-test` for masks/ranks/selectors |
| `check-gd-digital-out.py` | queued digital output and software PWM, including the stock 5 ms clock clamp |
| `check-gd-angles.py`, `check-gd-angle-data.py` | complete angle C bodies and separately counted 102-entry numeric table |
| `check-gd-trig.py`, `check-gd-trig-data.py` | complete sine/cosine C bodies and separately counted 131-entry sine table |
| `check-gd-timer-vendor.py`, `check-gd-timer-data.py` | timer SDK code/table byte gates; `--self-test` compares 7,483 modeled MMIO/ABI cases |
| `check-gd-dma-vendor.py`, `check-gd-interrupt-control.py` | complete DMA configuration and NVIC/SYSCFG control C spans |
| `check-gd-dma-control-mmio.py` | 10,177 stock-versus-candidate ordered MMIO/ABI cases with no mocked calls |
| `check-gd-analog-in.py`, `check-gd-buttons.py` | complete analog scheduling, GPIO ADC/DWT delay and button command/task spans |
| `check-gd-config-finalize.py`, `check-gd-config-finalize-model.py` | complete allocation/finalization command and 276 bounded final-state/call/ABI cases; services mocked |
| `check-gd-pwm-vendor.py` | complete signed-current/PWM setup and additional timer SDK bodies |
| `check-gd-debug-scope.py`, `check-gd-debug-scope-data.py` | JScope/RTT initialization and typed identifier/terminal-name constants |
| `check-gd-protocol-data.py` | typed ACK encoder and parser-error string, distinct from generated lookup data |
| `check-gd-platform-data.py` | independent compiled-object check for the shared APB prescaler table |
| `check-gd-scatter-runtime.py`, `check-gd-scatter-runtime-model.py` | C scatter helper byte gates and stock/synthetic ordered-memory behavior checks; oversized helpers remain standalone |
| `check-gd-gpio-output.py`, `check-gd-gpio-output-mmio.py` | GPIO and motor pseudo-pin C byte comparisons; 10,156 modeled ABI/MMIO cases |
| `check-gd-memory.py` | C microlib/AEABI body comparison with entry-alignment diagnostics and native `--self-test` |
| `check-gd-mpu.py`, `check-gd-board.py` | C MPU helpers and board cache/startup entry comparisons |
| `check-gd-board-mmio.py` | compare 72 stock/recovered MPU/cache MMIO/barrier cases using linked helpers; debug/scheduler handoffs mocked |
| `check-gd-runtime.py` | architectural startup/context assembly spans, counted separately from C |
| `check-gd-scatter-handlers.py` | proven assembly-origin scatter copy/zero spans; two C counterparts remain semantic references only |
| `check-gd-stepper-load-model.py` | 1,200 loader state/call/ABI cases; stock queue helpers and mocked GPIO/free |
| `check-gd-dq-limit-model.py` | 41,984 DQ output/FPSCR/ABI cases using the stock square-root dependency |
| `check-gd-sqrt-model.py` | positive square-root output/FPSCR/ABI checks; SDK hardware intrinsic compatibility is documented separately from C control flow |
| `check-gd-trig-model.py` | 34,816 finite sine/cosine output/write-order/FPSCR/ABI/alias cases plus eight bounded nonreturning cases; standalone sine is not validated |
| `check-gd-bss.py` | verify actual typed NOBITS object layout; unknown zero-region holes remain explicit |
| `emit-gd-ctr.py` | deterministically emit readable retained declaration strings and verify all 8,568 metadata/alignment bytes |
| `report-gd-progress.py` | audit saved mainBoardGD gates, freshness and non-overlapping source/function/data coverage |
| `check-gd-motor.py` | link recovered motor commands/helpers at stock addresses and compare complete code/pool extents |
| `check-gd-motor-reset-model.py` | 1,040 reset state/ordered-write/call/ABI cases with actual stock callees and an independent field oracle; candidate uses two following alignment bytes and remains unmatched |
| `check-gd-pi-model.py` | bounded PI-controller state, ordered-write, output/FPSCR and ABI comparison against actual stock instructions; modeled behavior is separate from byte equality |
| `check-gd-pwm-update-model.py` | 32,256 PWM-update ordered-MMIO, state-read, FPSCR and ABI cases; eight timer writes and pointer reloads preserved, without a hardware-waveform or byte-equality claim |
| `check-gd-motor-step-model.py` | 32,256 motor-step state/oracle, combined ordered-access, timer, FPSCR and ABI cases; `--self-test` rejects 13 stale-provenance/entry/extent mutations; not a hardware or byte-equality proof |
| `check-gd-stats-model.py` | 1,564 statistics arithmetic/state, ordered-access, call, reload and ABI cases; actual timer conversion with explicit encoder/send mocks; 13 provenance/entry/extent rejection tests |
| `check-gd-loop-b-model.py` | 37,888 full motor-loop-B caller state/access/call/FPSCR/ABI cases with explicit callee mocks; 19 provenance, IT-state, FP-context and negative-C controls |
| `check-gd-core.py` | compare FlashForge commands, IRQ, reset and DWT/SysTick timer source against complete stock function spans |
| `check-gd-gpio.py` | compare GPIO vendor/board helpers with volatile-register semantics and sensorless pin behavior |
| `check-gd-startup.py` | compare startup code and model stock/recovered MMIO traces with Unicorn; byte and semantic results are separate |
| `codegen-style.py` | count literal-pool, wide-immediate and prologue patterns to compare compiler families |
| `libscan.py` | match ARM archive members against stock code using direct archive/ELF parsing; run `--self-test` before trusting a miss |
| `compare-dict.py` | gate a rebuilt dictionary against a stock one |
| `compare-blob.py` | gate the compressed identify blob as stored in flash |
| `cmpfuncs.py` | count command handlers that are instruction-identical to stock; also the shared `norm()`, byte comparator and build-path resolution (`MCU_TREE`, overridable by `OURS_ELF`/`OURS_BIN`/`OURS_DICT`) every comparator imports |
| `shutdownmap2.py` | recover the shutdown error code of every instrumented site |
| `timertags.py` | recover the call-site tag passed to every sched_add_timer |
| `permute.py` | try source variants of one function against stock's instructions |
| `coverage.py` | how many of our functions appear instruction-exact anywhere in stock |
| `vtcmp.py` | gate the vector table: slot by slot, and its length |
| `addrdelta.py` | how far each handler is from stock's address, and the drift pattern |
| `linkorder.py` | derive stock's link order from the handler addresses |
| `classify2.py` | bucket the differing handlers by cause (allocation vs source) |
| `objalign.py` | score a symbol from any `.o` against the stock image |
| `fncmp.py` | compare one of our functions against a stock address: positional instruction score, then the raw bytes of the whole `nm -S` range; `EXACT` needs both, `INSTR-EXACT POOL-DIFF` flags a function whose code matches but whose literal-pool words do not |
| `sbs2.py` | side-by-side disassembly of one handler, ours against stock |
| `imgdiff.py` | whole-image positional byte comparison |
| `klip_cmdtab.py` | find `command_index[]` and map every command to its handler address |
| `armdis.py` | Thumb-2 disassembly of one function, literals and strings resolved |
| `xref.py` | literal-pool cross-references, to find what touches a global |
| `relocmap.py` | map every rebuilt function into stock, compare literal relocations, and rank unresolved compilation units |
| `permuter/` | drive [decomp-permuter](https://github.com/simonlindholm/decomp-permuter) against one function: `setup.sh` fetches it, `newtarget.sh` builds the target and base |
| `flagsweep.sh` | rebuilds a tree copy once per extra compiler switch and scores the open functions; how the flag question was closed |
| `lcscmp.py` | alignment-aware (longest-common-subsequence) instruction score for one function, with the same byte check and verdicts as `fncmp.py`, which counts positions and punishes an inserted instruction for the whole rest |

For the GCC-built boards, `objalign.py` is the toolchain oracle: pointed at `__udivmoddi4` from a
candidate `libgcc.a`, it settles which toolchain and multilib built the
stock image without compiling the firmware at all. That is how the FPU was
found.

MainBoardGD uses an ARM scatter-loading runtime and microlib, with
armclang-style code generation. Its dictionary's GCC version does not
identify the executable compiler. Extract its execution regions before
disassembly, and use the generated/layout JSON as stock reference data:

```sh
python3 tools/scatterload.py mcu/mainBoardGD/stock/mainBoardGD.bin 0x08000000 --out work/regions
python3 tools/extract-gd-layout.py mcu/mainBoardGD/stock/mainBoardGD.bin --out work/mainBoardGD-layout.json
python3 tools/extract-gd-generated.py --out work/mainBoardGD-generated.json
```

The generated-layer extractor requires Python 3 and Capstone, accepts
`--image PATH`, and can check supplied expanded regions with
`--itcm work/regions/00000000.bin --data work/regions/24000000.bin`.
Its output includes raw bytes, runtime addresses, all 49 command handlers,
18 encoders, 32 static strings, 144 declarations and the identify blob.
These are extracted artifacts, not rebuilt firmware. Both extractors run
without armclang or a licence. [The board plan](../mcu/mainBoardGD/PLAN.md)
records current limits and the matching gates.

**The permuter is how the last functions are being closed.** Once a
function is semantically right and differs only by register choice,
schedule or block layout, guessing source spellings by hand is slow;
decomp-permuter mutates the C at random (temporaries, statement order,
types, expression shapes) and scores every mutant's object against the
target, which is the standard technique in matching decompilation. Three
things had to be arranged before its scores meant anything here, and
`permuter/newtarget.sh` does all of them:

- **the target must be a relocatable object, not raw bytes.** `mktarget.py`
  re-emits the stock function with symbolic `bl`/`b.w` and `.word sym`
  literal-pool entries, so a candidate's relocations line up with it;
- **preserve the translation unit unless a reduction is verified.** GCC
  -O2 can inline other functions and delete stores to write-only statics,
  so stripping other bodies (the permuter's default) can change the
  target. The default base retains them and restores `noinline` on
  functions that must remain calls. The trigger's separately verified
  reduced scratch is a function-specific exception, not a general rule;
- **two attributes change code and pycparser cannot carry them:** a
  `noinline` function gets its attribute back through a prior prototype,
  and a static variable in a named `section` -- which GCC will not
  constant-fold, where the same variable without the attribute is folded --
  loses `static` instead.

`newtarget.sh` ends with the permuter's `--debug` pass; its base score must
reflect only the known difference before a run is worth starting. The
scorer does not check semantics: a mutant that deletes code can score
better, so every candidate is re-read before it goes into the tree.
`GPIO_InitPeripheral` was the first function it closed: the only change was
deleting an early `return` for an empty pin mask that the loop guard already
covers.

`eddy-sensor.md` is the full recovered description of the inductive sensor:
every claim cites the flash address of the instruction that justifies it.

`klip_cmdtab.py` resolves all 54 handlers on levelBoard and works on the
other three images too:

    ./tools/klip_cmdtab.py \
        mcu/levelBoard/stock/levelBoard.bin mcu/levelBoard/stock/levelBoard.dict.json 0x08004000
