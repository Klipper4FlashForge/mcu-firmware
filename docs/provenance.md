# The MCU firmware is Klipper

> Carried over from the Reforge firmware repository, where it is note 15.
> Cross-references to `bin/unpack.sh` and to the other numbered notes
> (`10-hardware.md` and so on) point back into that repository.

`20-klipper-fork.md` describes the FlashForge fork as host-side only, with
"closed prebuilt MCU firmware on the main/e/eheater/level boards". The first
half is right; the second half is worth restating. The boards are not a black
box — **all four run Klipper MCU firmware**, and their own images say so:

```
$ ./tools/extract-dict.py mcu/levelBoard/stock/levelBoard.bin
  app       Klipper (GNU GPLv3)
  version   ?-20260609_102247-zhengxiaomming
  built     gcc: (GNU Arm Embedded Toolchain 10.3-2021.10) 10.3.1 20210824
  mcu       stm32f103xe @ 128000000 Hz, 230400 baud
  54 commands, 24 responses
```

## Where the firmware lives

Not in `firmwareExe`. The MCU images ship in the **control** component
(`control-1.2.9.tar.xz`), which `bin/unpack.sh` extracts but nothing else
looks at. Its `run.sh` burns them over the same serial ports the app
handshakes on in `10-hardware.md`:

| image | board | flashed by | port | load addr |
|---|---|---|---|---|
| `mainBoardGD.hex` | main board | `ISPCommand` | — | `0x08000000` |
| `eBoard.hex` | carriage extruder | `IAPCommand` | `/dev/ttyS5` | `0x08010000` |
| `heaterBoard.hex` | hotend heaters | `IAPCommand` | `/dev/ttyS4` | `0x08010000` |
| `levelBoard.hex` | under-bed cylinder | `IAPCommand` | `/dev/ttyS7` | `0x08004000` |
| `VDS_V1.0.1_0.hex` | VDS accessory | `firmwareExe`, from `/media/` | — | `0x08005000` |

`IAPCommand` and `ISPCommand` ship alongside them, so the flashing protocol is
in hand too. The `*_fail.img` and `mcu.img` files are 800×480 framebuffer
splash screens, not firmware. VDS is the only one that is not Klipper.

## Why this matters

Klipper stores its data dictionary — every command, response, config constant
and pin enumeration — zlib-compressed inside the image. Nothing has to be
disassembled to learn the wire protocol; it decompresses straight out.

| board | MCU | clock | commands | of those, upstream |
|---|---|---|---|---|
| levelBoard | N32G45x (reports `stm32f103xe`) | 128 MHz | 54 | 47 |
| eBoard | `stm32f103xe` | 144 MHz | 77 | 69 |
| heaterBoard | `stm32f103xe` | 144 MHz | 78 | 71 |
| mainBoardGD | `gd32h757zg` | 600 MHz | 49 | 37 |

The FlashForge delta is seven commands on the three STM32 boards —
`get_mcu_version`, `set_trigger_threshold`, `get_basic_param`, `remove_peel`,
`get_emcu_pa_value`, `pa_action`, `endstop_recover_state` — and their host
side is already in the fork we ship (`extras/ff_eddy.py`,
`extras/pa_adjust.py`). The GD32 main board has five of the seven plus seven
`mclib_*` commands of its own, for closed-loop steppers.

The FlashForge additions come from one shared source file with a board
selector: `get_emcu_pa_value` is a real function on the eBoard and a bare
`bx lr` on the levelBoard, while its reply stays in both dictionaries.

The *upstream* underneath that file is not shared, though. eBoard carries a
`config_lis2dw` that upstream only introduced in October 2024; heaterBoard
still has the form that predates it, despite being built three weeks earlier.
Each board is rebased on its own schedule, so a version fingerprint from one
board says nothing about another.

This repository reconstructs the levelBoard source from upstream Klipper
`6d70050` plus a recovered patch, and `build.sh` gates the rebuild against the
stock image.

**The rebuild is byte-identical.** All 26,704 bytes, MD5
`156366b40ccc51f5768e083fa8ead210`, zero differing bytes; 247 of 247
functions and 7,093 of 7,093 instructions exact and at stock's own
address, all 54 command handlers, the data dictionary, the compressed
identify blob, the vector table, every literal pool and the RAM layout.
Verified from the committed tree, and again by lifting the recovery commit
onto a separate clone of upstream at `6d70050` with `git am`: same MD5.

The bytes are settled; the *source* is not. Six conditionals in the
recovered tree have two identical arms — four in `ff_eddy_check_trigger`,
one each in `ff_eddy_update` and the vendor `DMA_Init`. Each emits no
code and exists only to change how often a value is referenced, which is
what decides the register it gets. One such construct is a believable
engineer's slip; six is not, and their distribution is lopsided. So the
patch reproduces stock's bytes without being stock's source: real code
not yet recovered most likely supplied those references as a side
effect. Two signs point that way in `ff_eddy_check_trigger` alone.
Dropping its hysteresis-tail conditional changes the function's size by
four bytes, 264 to 268, which no register choice can do — so it stands
in for a code shape, not a spelling. And stock's two range checks use
opposite register pairs (`subs r3, r5, #1 / movw r2, #0xfffe` in the
hard arm at `0x08007CB6`, the reverse in the main arm at `0x08007CD0`),
where one source shape written twice gives the main arm's form both
times. `mcu/levelBoard/PLAN.md` carries that open question.

Getting there needed three things that are worth knowing about generally:

- **The build was not reproducible against itself.** Klipper stamps a
  timestamp and hostname into the dictionary it embeds, so two builds a
  second apart differ. And Fedora's Python links zlib-ng, whose deflate
  output differs byte for byte from classic zlib on identical input.
- **FlashForge instrument two things systematically**: `shutdown()` latches a
  per-site error code, and `sched_add_timer()` carries a call-site tag that
  names the culprit when a timer is scheduled late. Both were recovered in
  full from the image.
- **Message ids are baked into the image**, and Klipper assigns them from
  the order the `DECL_COMMAND` markers land in the `.ctr` section -- which is
  reverse lexical order within a file, independent of the order the bodies
  themselves are emitted in. Matching them pinned down exactly where in the
  source FlashForge put their commands: inside `basecmd.c`, between
  `clear_shutdown` and `identify`.

Getting the last functions into place needed a different tool than
reading disassembly: the matching-decompilation community's
*decomp-permuter*, which mutates C at random and scores each mutant's
object against the target. `tools/permuter/` sets it up for
this tree. Its first result was `GPIO_InitPeripheral`, closed by deleting
an early `return`; its most instructive one was `ff_eddy_update`, all 776
bytes of which now match. GCC had laid its whole smoothing path out of
line because the median helper used `memcpy()` -- a plain copy loop
leaves the helper pure, and the call heuristic no longer marks the branch
cold. The same function is where the placement of `return` statements
turned out to be a register lever: the early-return predictor sets the
branch probabilities that decide which address the allocator keeps in a
callee-saved register and where the epilogue gets copied. Its last
divergence, one callee-saved register swap, closed on a conditional that
emits no code at all -- both arms store the same value, so the arms are
cross-jumped and the compare deleted, but the reference it holds to the
tested variable survives into the register allocator and reorders the
colouring.

The last two functions closed on that same construct once the rule
behind it was understood: GCC's allocator drops the call-clobbered
registers from a value's preferred set when the cost of preserving it
across a call exceeds the value's memory cost, and that memory cost is
its own frequency-weighted reference count. So the lever is how often a
local is mentioned and in which block, not how long it lives -- and a
conditional with identical arms mentions one for free. The vendor
`DMA_Init` needed that plus two more: `int` rather than `uint32_t` field
locals, because the signed intermediate keeps a conversion in the tree
that reorders the allocator's work list, and each field read one group
ahead of its use.

## Three things found on the way

**`endstop_recover_state` cannot reply.** The handler calls
`ctr_lookup_encoder()` directly with a string literal instead of going through
Klipper's `sendf()` macro. That skips the `DECL_CTR` marker, so the reply
format is never registered as a response: the lookup returns NULL at run time
and the reply goes to `command_sendf(NULL, ...)`. FlashForge's own klippy
sends this command — `MCU_endstop._recover_cmd` in `klippy/mcu.py` — and all
three boards that carry it are affected.

**The USART interrupt sits on vector 36, and that should not work.** Stock
installs a handler that services USART1 — it reads the status register at
`0x40013800` and tests ORE/RXNE — at vector slot 36, and unmasks NVIC line
36. But the N32G45x CMSIS header numbers this part exactly like an F103: a
contiguous enum in which 36 is `SPI2_IRQn` and USART1 is 37, with the
N32-only interrupts appended from 53 up. Two SDK mirrors agree and there is
no gap in 11..37 to absorb an off-by-one.

That looks like a one-line bug, except the console is *not* DMA-driven — it
is upstream Klipper's byte-at-a-time interrupt path, and the DMA1 channel 4
and 5 handlers in the image are never configured, enabled or unmasked. If
the handler were really on SPI2's line the board could not receive a byte,
yet the printer works. So either the silicon numbers USART1 at 36 against
its own published header, or the image has a defect that ought to be fatal.
The binary cannot settle it; that needs the reference manual or a live
board.

**`RESERVE_PINS_serial` is `PH10,PH9`.** Upstream says `PA10,PA9` for USART1.
Port H does not exist on this family and does not appear in the image's own
pin enumeration, so the reservation silently matches nothing and PA9/PA10 stay
allocatable from `printer.cfg`. Deliberate, as far as anyone can tell from the
image.
