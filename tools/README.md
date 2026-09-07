# The tools

| | |
|---|---|
| `extract-dict.py` | pull the Klipper data dictionary out of a raw image |
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

`objalign.py` is the toolchain oracle: pointed at `__udivmoddi4` from a
candidate `libgcc.a`, it settles which toolchain and multilib built the
stock image without compiling the firmware at all. That is how the FPU was
found.

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
