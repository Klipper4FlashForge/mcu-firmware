# mainBoardGD startup and layout

Assembly-checked record, 2026-09-09. Addresses below are execution
addresses. The input is `stock/mainBoardGD.bin`, MD5
`fb64911bac422a27d7ed7fab3597603f`. This describes stock; it is not a
reconstructed linker script or a passing layout comparison against a build.

Run from the repository root:

```sh
python3 tools/extract-gd-layout.py mcu/mainBoardGD/stock/mainBoardGD.bin --out work/mainBoardGD-layout.json
python3 tools/scatterload.py mcu/mainBoardGD/stock/mainBoardGD.bin 0x08000000 --out work/regions
```

The first command emits JSON directly from stock, checks its digest,
decodes all vectors and scatter records, and finds the cross-region
`movw ip; movt ip; bx ip` veneers. It needs no disassembler or compiler.
The second writes the expanded regions for further analysis.

## Regions and boot order

The `Region$$Table` begins at flash `0x08003744`:

| Source | Destination | Expanded bytes | Operation |
|---|---|---:|---|
| `0x08003778` | `0x24000000` | 11,912 | decompress, consuming 3,225 source bytes |
| `0x08004418` | `0x00000000` | 28,120 | copy |
| ignored by zero helper | `0x24002e88` | 33,976 | zero |

Initial SP is `0x2400b340`. Reset at `0x080003b8` clears initial RAM,
calls `SystemInit` at `0x08000620`, and enters `__main` at `0x080003a4`.
The runtime invokes `__scatterload` at `0x080004c8` before entering ITCM
`main` at `0x000038b0`. See [recon.md](recon.md) for the runtime helper
identification and `main`'s MPU/cache setup.

The vector table occupies `[0x08000000, 0x080003a4)`: 233 slots including
SP. Of the remaining slots, 14 contain non-default handlers, 159 point
at default handler `0x080003e4`, and 59 are zero. "Non-default" records
the vector target; it does not prove an interrupt is enabled at runtime.

| External IRQ | Vector slot | Thumb pointer | Execution address |
|---:|---:|---|---|
| 11 | 27 | `0x00000081` | `0x00000080` |
| 12 | 28 | `0x000000c9` | `0x000000c8` |
| 18 | 34 | `0x00000001` | `0x00000000` |
| 37 | 53 | `0x00000221` | `0x00000220` |

These are the only non-default external vectors. IRQ18's pointer is
**one**, not a null vector: stripping the Thumb bit yields a real
function at ITCM zero. Its first instruction is `push {r4, lr}` and its
body accesses peripherals and motor state. Do not discard address zero
when building symbol maps or resolving code pointers.

The extractor finds 45 flash-to-ITCM and 41 ITCM-to-flash veneers. Their
86 decoded target addresses agree with an independent Capstone decoding
in this session. These bridges must be represented in any layout model;
a direct branch substituted for a veneer changes the image.

## SystemInit requires volatile register reads

`work/mainBoardGD-ghidra.c` is a navigation aid, not a faithful C source
for `SystemInit`. In particular, its variable `uVar1` captures
`0x58024408` before the clock-switch writes, and its final loop tests that
stale value. The machine code reloads the register on every iteration.
The export also folds intermediate register writes into expressions and
loses the repeated status reads around the oscillator wait.

`work/flash.lss` establishes the actual loads:

| Instruction address | Register read | Use |
|---|---|---|
| `0x08000648` | `0x58024400` | readiness wait; back edge `0x08000650` |
| `0x08000758` | `0x58024400` | bounded readiness wait; back edge `0x08000768` |
| `0x0800076a` | `0x58024400` | fresh status check after that wait |
| `0x08000814` | `0x58024400` | readiness wait; back edge `0x0800081a` |
| `0x0800082c` | `0x58024408` | clock-switch status wait; back edge `0x08000834` |

The first four use `[r0, #-8]`, with `r0 = 0x58024408`. The last uses
`[r0]`, masks `0x0c`, and waits for `0x0c`. Recover each hardware access
as volatile and preserve the write/read order. Peripheral names and
clock-frequency calculations still need matching against the GD32H7
register definitions; the table alone does not establish a complete
600 MHz clock configuration.

## The generated init runner ends before the next function

The Ghidra export labels `ctr_run_initfuncs` at `0x000027c8` with
`size=268` and folds serial setup into its body. The assembly gives a
26-byte instruction range `[0x27c8, 0x27e2)`, followed by six zero bytes
to the next function at `0x27e8`: a 32-byte slot including padding.

| Call instruction | Target | Role |
|---|---|---|
| `0x000027ca` | `0x000007a8` | first init call |
| `0x000027ce` | `0x00003878` | second init call |
| `0x000027d2` | `0x00004ec8` | third init call |
| `0x000027d6` | `0x00003d00` | motor init wrapper |
| `0x000027de` | `0x000045a0` | tail call into serial init |

The call at `0x00003d06` reaches veneer `0x00005c02`, whose destination
is flash `0x08001710`. Ghidra calls that flash routine `mclib_init`, but
the generated init runner calls the **ITCM wrapper** at `0x00003d00`.
The wrapper also initializes per-motor states, currents and microsteps;
using only the flash routine as the generated init callback loses work.
Keep these two symbols distinct in recovered source. The
[motor-control account](motor-control.md) describes the wrapper's state
and API relationships.
