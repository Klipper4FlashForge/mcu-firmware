# mainBoardGD: first reconnaissance

What the image is, how it is laid out, and the one finding that changes the
plan: **this board was not built by the toolchain its own dictionary names.**

Everything below is derived from `mcu/mainBoardGD/stock/mainBoardGD.bin`
(45,552 B, MD5 `fb64911bac422a27d7ed7fab3597603f`) and nothing else.

## 1. It is not a flat image

Loading the file at `0x08000000` and disassembling straight through is
wrong past the first 17 KB, and the vector table says so on the first
read: most of its handlers are single-byte-range addresses.

    offset 0x00  0x2400b340   initial SP        (RAM at 0x24000000)
    offset 0x04  0x080003b9   Reset             (flash)
    offset 0x08  0x00000129   NMI               (address 0 -- ITCM)
    offset 0x0c  0x00000119   HardFault
    ...          0x080003e5   the default handler, everywhere else

Cortex-M7 aliases its instruction TCM at `0x00000000`. The handlers live
there, so a *second* image is copied into ITCM before anything runs. The
copy is driven by a table at `0x08003744`:

| src | dst | size | via |
|---|---|---:|---|
| `0x08003778` | `0x24000000` | 11,912 | `__decompress` at `0x080004ec` (3,225 compressed) |
| `0x08004418` | `0x00000000` | 28,120 | `__scatterload_copy` at `0x0800335a` |
| — | `0x24002e88` | 33,976 | `__scatterload_zeroinit` at `0x0800336a` |

`{src, dst, size, fn}` quadruples walked by a loop at `0x080004c8` that
`orr`s the thumb bit onto `fn` and calls it: that is **`Region$$Table` and
`__scatterload`**, and they are ARM Compiler (armlink / Keil MDK) runtime,
not GNU. Boot order is `Reset` (`0x080003b8`, zero 32 KB at `0x24000000`)
→ `SystemInit` (`0x08000620`, GD32 clock tree) → `__main` (`0x080003a4`,
sets SP, `__scatterload`) → `main` in ITCM at `0x000038b0`.

`tools/scatterload.py` does all of this and writes the regions out:

    ./tools/scatterload.py mcu/mainBoardGD/stock/mainBoardGD.bin 0x08000000 --out work/regions

So the image is three things, not one:

| file range | what | analyse at |
|---|---|---|
| `0x08000000`–`0x08003744` | vector table, startup, ARM C runtime, and ~11 KB of flash-resident code (the motor library) | `0x08000000` |
| `0x08003778`–`0x08004418` | LZ77-compressed `.data` | `0x24000000` after expansion |
| `0x08004418`–`0x0800b1f0` | the ITCM image: Klipper's code *and* its rodata, including the identify dictionary | `0x00000000` |

`main` at `0x000038b0` configures the MPU and enables the I- and D-caches
through CMSIS's `ARM_MPU_*` / `SCB_Enable*Cache` sequences before calling
`sched_main` at `0x00004238`.

Named so far, and used throughout below:

| ITCM | | flash | |
|---|---|---|---|
| `0x000038b0` | `main` | `0x080003a4` | `__main` |
| `0x00004238` | `sched_main` | `0x080003b8` | `ResetHandler` |
| `0x000027c8` | `ctr_run_initfuncs` | `0x08000620` | `SystemInit` |
| `0x000027e8` | `ctr_run_shutdownfuncs` | `0x080004c8` | `__scatterload` |
| `0x00002810` | `ctr_run_taskfuncs` | `0x080004ec` | `__decompress` |
| `0x000021a0` | `ctr_lookup_encoder` | `0x0800335a` | `__scatterload_copy` |
| `0x00002420` | `ctr_lookup_static_string` | `0x0800336a` | `__scatterload_zeroinit` |
| `0x00001ca8` | `command_sendf` | `0x08000458` | `strcmp` |
| `0x00004410` | `sched_shutdown` | `0x08000488` | `setjmp` |
| `0x00005580` | `timer_read_time` | `0x080004a2` | `longjmp` |

`sched_main` is upstream's, plus one FlashForge line: on the shutdown path
it sends `GDMainboard close=%hu Close_num=%hu Temp_waketime=%hu` before the
`shutdown` message.

## 2. The toolchain contradiction

The dictionary says:

    gcc: (GNU Tools for Arm Embedded Processors 7-2018-q2-update) 7.3.1 ...
    binutils: (2.34-4ubuntu1+13ubuntu1) 2.34

The image says armlink. Both are true, and the way they are both true is a
**two-stage build**:

- Klipper's `Makefile` derives `build_versions` from `$(CC);$(AS);$(LD);...`
  at the point where `buildcommands.py` runs — the step that produces
  `out/klipper.dict` and `out/compile_time_request.c`. That step ran under
  arm-none-eabi-gcc 7.3.1 and GNU ld 2.34 on a machine called `ubuntu`.
- The firmware that ships was compiled and linked by the ARM Compiler
  (armclang, §8), from sources that include the generated
  `compile_time_request.c`.

Three independent observations confirm the two stages are not in step —
see §4. Practically: **`objalign.py` against a GCC 7.3.1 libgcc will not
settle this board's toolchain, because GCC did not build it.** The
levelBoard method's first gate does not apply here as written.

## 3. The whole `.compile_time_request` survives in the image

Klipper's `DECL_*` macros emit NUL-terminated strings into a
`.compile_time_request` section. Nothing references them, so a GNU link
with `--gc-sections` drops them — the levelBoard, eBoard and heaterBoard
images contain none. This linker kept them, so 8.5 KB of `.data` at
`0x24000010` is the board's *entire* build description, in link order.
It is recovered verbatim in
[`compile-time-request.txt`](compile-time-request.txt) (144 requests):

    ./tools/extract-ctr.py work/regions/24000000.bin

That single artifact pins, without disassembling anything:

- **the source file set and link order** — `stepper.c`, `command.c`,
  `basecmd.c`, `gpiocmds.c`, `debugcmds.c`, `endstop.c`, `initial_pins.c`,
  `trsync.c`, `adccmds.c`, the `mclib` unit, `buttons.c`, `serial`,
  `timer`, `watchdog`, `gpio`, `adc`;
- **the order of the declarations inside each file**, which is what the
  levelBoard job had to infer;
- every task, init and shutdown function by name (`mclib_init`,
  `trsync_task`, `analog_in_task`, `buttons_task`, `console_task`,
  `timer_task`, `watchdog_reset`, `timer_cnt_init`, `serial_init`,
  `initial_pins_setup`, `clear_active_irq`, `alloc_init`, `move_reset`, …);
- `DECL_ARMCM_IRQ SysTick_Handler -1` and `DECL_ARMCM_IRQ
  USART0_IRQHandler +0x25` — the only two IRQs Klipper itself claims.

The FlashForge block sits inside `basecmd.c` exactly as it does on the
levelBoard, between the upstream commands, but in a different order and
with a different membership: `identify`, then `get_pa`, `pa_action`,
`remove_peel`, `get_mcu_version`, `get_basic_param`. Note the handler is
named `command_get_pa` here where the levelBoard has
`command_get_emcu_pa_value`, and there is no `set_trigger_threshold`.

## 4. The generated layer is not folded, and it does not match the sources

Klipper resolves a message format to its encoder through a *generated*
function:

    #define _DECL_ENCODER(FMT) ({ DECL_CTR("_DECL_ENCODER " FMT);   \
                                  ctr_lookup_encoder(FMT); })

`buildcommands.py` emits `ctr_lookup_encoder` as an `__always_inline`
chain of `__builtin_strcmp` against literal strings, which GCC folds to a
single constant at every `sendf` site — that is why the levelBoard image
contains no format strings and no lookup function.

**This build did not fold it.** `ctr_lookup_encoder` is a real 496-byte
out-of-line function at ITCM `0x000021a0` that calls `strcmp` against 18
literal strings, and every `sendf` passes the format string to it at run
time. `command_get_basic_param` at `0x00001690` is the whole pattern in
seven instructions:

    1690  push  {r7, lr}
    1692  adr   r0, 0x16a4        ; "param_value value=%u reserve=%u"
    1694  bl    0x21a0            ; ctr_lookup_encoder
    1698  movs  r1, #0
    169a  movs  r2, #0
    169c  ldmia sp!, {r7, lr}
    16a0  b.w   0x1ca8            ; command_sendf

`ctr_lookup_static_string` at `0x00002420` (792 bytes) and the encoder
table at `0x00005d08` (18 entries, ending exactly where the identify blob
begins at `0x00005d98`) are out of line for the same reason. The whole
generated layer — every string, every table — is therefore readable
straight out of the image, which no GCC-built Klipper gives you.

And reading it shows the generated layer does **not** describe the sources
compiled beside it. Three measurements:

1. `ctr_lookup_encoder` knows 18 messages. The image's `.ctr` declares 19
   distinct ones. The odd one out is `param_value value=%u reserve=%u` —
   the message `command_get_basic_param` asks for above. The lookup falls
   through and returns `NULL`, so `get_basic_param` calls `command_sendf`
   with a null encoder. There is no clean null trap to catch it: address 0
   is mapped ITCM, so the struct is read out of `IRQ18_Handler`'s first
   instructions — `encoded_msgid` 0xb510, `max_size` 0xf2, `num_params`
   0x42, `param_types` 0x21040044, which is not mapped. The dictionary
   agrees with the lookup and not with the `.ctr`: 18 responses, no
   `param_value`. Whatever `get_basic_param` does on this board, it does
   not answer.
2. `ctr_lookup_static_string` disagrees with nothing: all 32
   comparisons are string-for-id identical to the dictionary's
   `static_string_id` enumeration, with IDs 2–33. The final comparison
   maps `Not a valid ADC pin` to 33; unmatched strings separately return
   255. `extract-gd-generated.py` executes every matching path and the
   fall-through to check this. So the
   drift is not general — it is one function's body.
3. Klipper numbers commands from `.ctr` order, so walking this image's
   `.ctr` should give a strictly *descending* dictionary id within each
   translation unit. It does, for every file — `stepper.c` 28→23,
   `gpiocmds.c` 22→18, `debugcmds.c` 17→14, `endstop.c` 31→29,
   `trsync.c` 35→32, `adccmds.c` 37→36, the `mclib` unit 49→43,
   `buttons.c` 41→38 — and breaks in exactly one place, the FlashForge
   block inside `basecmd.c`, which runs `5, 4 | 6, 2 | 3`. The order the
   ids imply there is `remove_peel, get_emcu_pa_value, pa_action,
   get_basic_param, get_mcu_version`: **the levelBoard's order**, not this
   image's.

Both compilers emit `.ctr` entries in the same direction (every other file
proves it), so a within-file reordering is a source change, not a
compiler difference. The generated files were produced from an earlier
snapshot of the shared FlashForge tree; the GD32 sources were then
reordered and `get_basic_param` given a reply, and nothing was
regenerated. **Gate on the `.ctr`, never on the dictionary.**

## 5. The command table, and 49 named handlers

`command_index[]` is at ITCM `0x6560`: 50 entries of 16 bytes
(`uint16 encoded_msgid; uint8 num_args, flags, num_params; const uint8
*param_types; void (*func)(uint32_t*)`), ids 1–49 plus a null entry.
Walking it names every handler; the map is in
[`handlers.md`](handlers.md). `tools/klip_cmdtab.py` resolves all 49 of 49
against the extracted ITCM region and finds nothing at all against the raw
image -- the layout was the whole obstacle. Cross-checked against
`oid_alloc(oid, command_config_*, size)` calls, which pass the config
handler's own address as the oid type tag — `command_config_mclib` at
`0x00000e40` tags with `0xe41`, and every `mclib_*` handler looks up
`0xe41`.

The FlashForge commands are thin on this board:

| command | handler | what it does |
|---|---|---|
| `get_mcu_version` | `0x1778` | sends the constants `year=2026 date=627 version=7092` |
| `get_basic_param` | `0x1690` | sends `param_value value=0 reserve=0` — constants |
| `get_emcu_pa_value` | `0x17c0` | sends one global |
| `pa_action` | `0x1a08` | stores its two arguments in two globals |
| `remove_peel` | `0x1c18` | `bx lr` — an empty stub |

(The levelBoard's `get_mcu_version` reports `7091` for 1.9.7; this is
`7092`. The dictionary's own stamp is `?-20260529_142047-ubuntu`, a month
before the `627` the version constant claims.)

## 6. `mclib` is a field-oriented closed-loop stepper controller

Seven commands and a `stepper` enumeration (`stepper_x`, `stepper_y`,
`stepper_z`, `extruder`) that upstream Klipper has no equivalent for. What
the code says, from `command_config_mclib` at `0x00000e40`:

    rs  = args.rs / 1000        # milliohms  -> ohms
    ls  = args.ls / 1e6         # microhenry -> henry
    km  = args.km / 1e6 / 50
    Kp  = ls * 6283.186         # = L * 2*pi*1000 rad/s -> a 1 kHz current loop
    Ki  = Kp * (rs / ls) * 5e-5 # * Ts, so Ts = 50 us -> a 20 kHz control loop
    a   = 1 - rs * 5e-5 / ls    # the discretised RL current plant
    b   = 5e-5 / ls

`Kp`/`Ki` are written twice into the per-motor state (offsets `0xa1,0xa2`
and `0xac,0xad`) — two axes, d and q. That is a textbook FOC current
regulator: a PI loop per axis, tuned from the motor's own R and L, at
20 kHz.

The two lookup tables in flash are the pair a FOC loop needs and nothing
else does:

| address | entries | contents |
|---|---:|---|
| `0x0800338c` | 101 | `atan(i/100)`, `i = 0..100`, to a max error of 1.2e-7 |
| `0x08003530` | 129 | `sin(i * 2*pi/512)`, `i = 0..128` — a quarter wave, with a guard entry either side |

An arctangent over `[0,1]` plus a quarter sine at 512 steps per electrical
revolution is an `atan2` and a Park rotation. The rest agrees: the DMA0
interrupts `IRQ11`/`IRQ12` (`0x40020000`) drive the loop, and the hardware initializer
at `0x08001710` configures four PWM outputs each on GPIOA/B/C
(`0x58020000`/`0x400`/`0x800`) against timers at `0x40010400` and
`0x40000800`.

The `.ctr`-declared `mclib_init` is the ITCM wrapper at `0x00003d00`:
it calls that flash initializer, then sets each motor's initial current
and microstep settings. Ghidra labels both routines `mclib_init`; those
labels are not evidence that the original source used the same name.

The library itself is the ~11 KB of **flash**-resident code at
`0x08000550`–`0x08003350`; the Klipper side runs from ITCM and calls into
it. `mclib_identify_motor` at `0x00001900` looks up its oid and returns —
the command exists, the feature does not, in this build.

## 7. SEGGER RTT is compiled in

`"Terminal"` at `0x08003737`, `"JScope_i2i2i2i2"` at `0x08000b68`, and the
control block id stored word-reversed at `0x0800337e` (`TTR REGGES`) are
SEGGER RTT's up-buffer names and its deliberately obfuscated `SEGGER RTT`
marker. `JScope_i2i2i2i2` is a J-Scope channel declaration: four `int16`
streams. Someone tuned this motor loop over a J-Link.

## 8. Which ARM Compiler: armclang, on the codegen

`Region$$Table` and `__scatterload` say *armlink*, which both ARM Compiler
5 (armcc) and ARM Compiler 6 (armclang) use. The code says armclang.
Counting two habits over the whole of each image — with the three
GCC 10-built boards in the same repository as the control:

| image | toolchain | `movw` | `ldr rN, [pc, …]` | `push {r7, lr}` |
|---|---|---:|---:|---:|
| levelBoard | GCC 10.3 | 17 | 636 | 0 |
| eBoard | GCC 10.3 | 51 | 902 | 0 |
| heaterBoard | GCC 10.3 | 38 | 751 | 0 |
| **mainBoardGD** | ? | **751** | **53** | **27** |

`tools/codegen-style.py` counts them; the mainBoardGD row is its two code
regions added together, since neither is the whole image:

    ./tools/codegen-style.py mcu/levelBoard/stock/levelBoard.bin 0x08004000 \
        work/regions/00000000.bin 0x0

The ratio inverts. GCC builds 32-bit constants from a literal pool;
this image builds them with `movw`/`movt` pairs and barely has pools —
LLVM's default, and not armcc 5's, which pools like GCC does. The second
column is the giveaway on its own: `push {r7, lr}` is LLVM keeping r7 as
the frame register, it appears 27 times here and *never once* in any of
the three GCC images. The tail-call epilogue agrees: ten sites do
`ldmia.w sp!, {r7, lr}` followed by `b.w`, which is how LLVM leaves a
tail call and is not a shape GCC or armcc emits.

So: **ARM Compiler 6 — armclang plus armlink** — on Ubuntu, with GCC 7.3.1
present only to run `buildcommands.py`. That is a strong reading of the
codegen, not a proof; the version is still open. The flash region counts
the same way as the ITCM region, so `mclib` came through the same compiler
— it is not a prebuilt library dropped in.

### The C library is microlib, and microlib does not date it

The way to pin a toolchain is the `objalign.py` argument in a different
library: routines the image took from the C library must appear in that
library byte for byte. `tools/libscan.py` does it — it reads `ar` archives
and ELF section tables directly, because Arm names its code sections
`!!!scatter`, `!!handler_copy`, `!!dclz77c`, and `objcopy -O binary -j`
writes an *empty file* for those without failing, which turns every
comparison into a false negative. It carries a `--self-test` for exactly
that reason; run it before trusting a miss.

Arm's own downloads are geoblocked from here (`artifacts.keil.arm.com`
answers 403 "blocked from your country", `keil.arm.com` 451), but Docker
Hub is not, and two community images carry real installers:
`fetiu/armclang:6.16` ships Arm's own
`ARMCompiler6.16_standalone_linux-x86_64.tar.gz`, and `elecboy/keil`
carries a Keil MDK with ARMCC (RVCT5.06 build 34) and ARMCLANG 6.7.

**Every runtime routine in the image is microlib** — the `mc_*.l`
archives, `--library_type=microlib`, not the default `armlib`:

| image | bytes | member |
|---|---:|---|
| `0x080003f4` | 64 | `mc_w.l:memmovea.o` |
| `0x08000458` | 28 | `mc_w.l:strcmp.o` |
| `0x08000474` | 20 | `mc_w.l:memchr.o` |
| `0x08000488` | — | `f_2.l:setjmp.o` (to the `nop.w` armlink patched over the FP save) |
| `0x080004c8` | 24 | `mc_w.l:init.o` — `__scatterload` |
| `0x080004ec` | 94 | `mc_w.l:__dclz77c.o` — `__decompress` |
| `0x0800335a`, `0x0800336a` | 14 each | `mc_w.l:handlers.o` — `__scatterload_copy`, `__scatterload_zeroinit` |

`mc_w.l` covers all of them, so that is the multilib. This is why the
helpers looked wrong against `armlib` (§8 above): armlib's are the
IT-block, four-register, position-independent versions; microlib's are the
small ones, and the small ones are what the image has. `__main` at
`0x080003a4` agrees — it sets `sp` from a literal, calls `__scatterload`
and jumps straight to `main`, with no `__rt_entry`, no `__rt_lib_init` and
no `exit`.

**But microlib does not date the build.** Inverting the search — every
library member whose code appears verbatim anywhere in the image — returns
*the same eleven members, at the same eleven offsets*, from all three
libraries:

| library | code blobs | matched in image |
|---|---:|---|
| ARM Compiler 6.16 | 75,795 | 11 members, 404 bytes |
| ARM Compiler 6.7 | 118,152 | 11 members, 404 bytes |
| RVCT 5.06 (armcc) | 99,605 | 10 members, 390 bytes |

The one difference is that AC5.06 has no `mc_8.l`, an archive that is
absent rather than different; the bytes it would contribute are identical.
Microlib is frozen across a decade of releases, so **no library comparison
can pin the version.** Nothing further is owed to this line of attack.

What that leaves settled: **armclang, armlink, `--library_type=microlib`,
multilib `mc_w`.** The version has to come from armclang's own output on
Klipper's source, which is the rebuild itself.

### Blocked on a licence, not on a download

`work/ac6/AC616/bin/armclang` and `armlink` are on disk and are the real
binaries, but both refuse to run:

    armclang: error: Failed to check out a license.
    armclang: note: ARMLMD_LICENSE_FILE is not set.

So the next thing needed is not another download but an **`ARMLMD`
licence**, which Arm gives away with MDK-Community for non-commercial use.
With one, the version sweep becomes an ordinary experiment: compile a
Klipper file at `-O2` with each candidate armclang and compare against the
image, exactly as the levelBoard job did with GCC.

## 9. The upstream base: the same commit as the levelBoard

Step 1 of the method wants an upstream commit whose declarations reproduce
the image's. The `.ctr` answers it directly, and the answer is that
**nothing new has to be found** — `6d70050` (2024-06-18), the commit the
levelBoard job already pinned, serves this board too.

Comparing the recovered `.ctr`, file by file and in order, against the
levelBoard tree's own per-file `out/src/*.o.ctr`:

| file | result |
|---|---|
| `command.c` | identical |
| `debugcmds.c` | identical |
| `initial_pins.c` | identical |
| `trsync.c` | identical |
| `adccmds.c` | identical |
| `buttons.c` | identical |
| `gpiocmds.c` | identical |
| `stepper.c` | identical but for `DECL_CONSTANT STEPPER_BOTH_EDGE +0x00000001` |
| `endstop.c` | identical but for `endstop_recover_state` |
| `sched.c` | identical but for `GDMainboard` where the levelBoard says `Levelboard` |
| `basecmd.c` | the FlashForge block, per §4 |

Seven upstream files match entry for entry. Of the four that do not, three
are known FlashForge deltas and the fourth is not a version difference at
all: `STEPPER_BOTH_EDGE` is declared under `CONFIG_HAVE_STEPPER_BOTH_EDGE`,
so its absence says the GD32H7 port does not offer step-on-both-edges, not
that the source is older.

Independently, the interval is bounded from both ends:

- **Not before `589bd64ce` (2024-06-05, "command: Support 2-byte message
  ids").** That commit widened `command_parser.encoded_msgid` from
  `uint8_t` to `uint16_t`. The image's `command_index[]` entries are
  16 bytes with a 16-bit id at offset 0 (§5), which is the post-commit
  layout.
- **Not after `41bc240b1` (2026-02-11, "adccmds: Support batching multiple
  reports").** That commit added `bytes_per_report=%c` to
  `query_analog_in`; the image's form has no such parameter. Nor does it
  have `analog_in_attach_trigger_analog`, added three days later.

`6d70050` sits thirteen days into that window. Every upstream commit
between `589bd64ce` and `41bc240b1` that touches the shared files is a
stepper timing or scheduler change that leaves the `.ctr` alone, so the
declaration-level evidence cannot narrow further — but it does not need
to. **The base is settled; the toolchain is the only gate left.**

## 10. What this means for the recovery

The board README's premise needs revising. In the levelBoard's order of
work:

- **Step 1 (dictionary → upstream commit)** is **done**, and it came out
  better than planned: the `.ctr` gives the file set, the link order and
  the declaration order directly, which is more than the dictionary can,
  and it puts the base at the levelBoard's own `6d70050` (§9). The
  dictionary itself is stale (§4) and must not be used as the gate.
- **Step 3 (settle the toolchain with `objalign.py` against GCC 7.3.1
  libgcc)** is void as written. The target is an ARM Compiler 6 build
  (§8); what remains is the *version*. The runtime comparison already
  identifies microlib but does not distinguish the candidate compiler
  versions. Compile controlled source samples with a licensed armclang
  and compare its output; do not repeat the library sweep to date it.
- **Step 4 (layout)** has to model three load regions and a scatter file,
  not one linker script, and has to place objects into ITCM.
- The `mclib` unit is not Klipper and has no upstream. It is ~11 KB of
  flash-resident FOC code with no public counterpart found; it will have
  to be reconstructed from the disassembly or left as the last piece.

Reproducing this image byte-for-byte therefore needs a toolchain nobody
has pinned yet and a GD32H7 port nobody has written.

Against that, this board gives back more than the others do. The three
GCC-built images hide their generated layer entirely: `--gc-sections` eats
the `.ctr`, and `-O2` folds `ctr_lookup_encoder`, `ctr_lookup_output` and
`ctr_lookup_static_string` into constants. This one keeps all of it. What
is already recovered from the image alone, with no compiler in the loop:

| | |
|---|---|
| the `.ctr` | §3 — file set, link order, declaration order, every task/init/shutdown by name |
| `command_index[]` | §5 — all 49 handlers, their arg counts and flags |
| the encoder table | §4 — 18 messages, msgid, max size, param types |
| `ctr_lookup_static_string` | §4 — all 32 shutdown strings and their ids |

That is the whole of `out/compile_time_request.c` in everything but
syntax. Whoever writes the GD32H7 port will not have to guess at any of
it — the open problems are the toolchain, the port, and `mclib`.

The executable extraction and the next recovery gates are in
[`../PLAN.md`](../PLAN.md). The command semantics and motor consumers are
recorded in [`motor-control.md`](motor-control.md); vector and branch-veneer
maps, startup boundaries, and decompiler corrections are in
[`startup-layout.md`](startup-layout.md).

## Reproducing this reconnaissance

    ./tools/extract-dict.py mcu/mainBoardGD/stock/mainBoardGD.bin work/mainBoardGD.dict.json
    ./tools/scatterload.py mcu/mainBoardGD/stock/mainBoardGD.bin 0x08000000 --out work/regions
    ./tools/extract-ctr.py work/regions/24000000.bin
    python3 tools/extract-gd-generated.py --out work/mainBoardGD-generated.json
    python3 tools/extract-gd-layout.py mcu/mainBoardGD/stock/mainBoardGD.bin --out work/mainBoardGD-layout.json

Ghidra needs the split image and the ITCM block, or it analyses 28 KB of
code at the wrong addresses. `work/gh/` holds the scripts used here:
import `work/gh/flash.bin` at `0x08000000`, add `work/gh/itcm.bin` as an
initialised block at `0x00000000` and RAM at `0x24000000`, seed the names
from `work/gh/names.txt`, then decompile. 361 functions come out into
`work/mainBoardGD-ghidra.c` (not in git).
