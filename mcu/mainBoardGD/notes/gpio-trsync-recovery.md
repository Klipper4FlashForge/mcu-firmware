# GPIO pseudo-pins and trigger-sync

Stock mainBoardGD MD5 `fb64911bac422a27d7ed7fab3597603f` is the reference.
Common ATfE flags are unchanged. Complete code/pool comparisons and behavioral
models are separate checks; neither substitutes for whole-image equality.

## GPIO ABI and effects

The 12-byte output handle has a byte pin tag, three padding bytes, a GPIO
pointer and a word bitmask. Setup uses the hidden AAPCS result pointer.
Setup's pin argument and output values are full 32-bit words: stock compares
the untruncated pin against 159 at `0x30f2`/`0x32bc`. Values pass unchanged
through reset/write to motor direction. Only the direction leaf's STRB
truncates to a byte. Input setup narrows pull-up to signed eight bits at the
peripheral call. Treating these arguments as byte parameters changes behavior
for values such as 256 and was corrected from the instruction evidence.

Every output write/toggle first accesses physical GPIO, including pseudo-pins.
Reset additionally configures AF/mode/pull/output type/speed, with IRQ save and
restore. Its port lookup uses the tag independently of the supplied handle;
there is no invalid-tag guard to invent in that path.

| Pin tags | Additional logical effect |
|---|---|
| `0x90, 0x94, 0x98, 0x9c` | Toggle's rising level dispatches Y/X/Z/extruder steps when both inhibit bytes are zero |
| `0x91, 0x95, 0x99, 0x9d` | Direction updates after physical reset/write/toggle |
| `0x92, 0x96, 0x9a, 0x9e` | Write disables the corresponding controller for nonzero value, enables it for zero |
| `0x72, 0x73` | Write boolean step-inhibit bytes at `0x24008b38/39` |

Both inhibit byte reads are short-circuited as in stock. These are hexadecimal
pin IDs, not decimal 72/73. GPIO direction/step/disable/enable veneers are
`0x5b9e/0x5ba8/0x5bb2/0x5bbc`, reaching flash
`0x08000b78/0x08001670/0x08000b80/0x08000bb8` respectively.

`gpio_output.c` covers full stock extents: input setup 104 bytes at `0x30f0`,
reset 264 at `0x31b0`, output setup 104 at `0x32b8`, toggle 266 at `0x3320`,
and write 846 at `0x3430`. Candidates are 104/284/96/286/230 bytes. None is
byte-exact; reset/toggle cannot fit and remain standalone-only. The large
write difference includes stock's repeated jump-table/condition chains.

`check-gd-gpio-output-mmio.py` compares 10,156 stock/candidate ARM executions:
all byte pin tags for write/toggle, all setup pins plus invalid high-word
values, full-width values including 256/high bit, physical levels, and four
inhibit combinations. It checks ordered MMIO, motor arguments, IRQ calls,
inhibit-byte access order and returned handle fields. Reset is tested only
on 144 constructible tags; stock's null/OOB reset inputs are not assigned
invented semantics. Motor/clock/peripheral/IRQ bodies and setup's reset call
are mocked; padding and interrupt/timing effects are not modeled.

Motor direction and enable now match complete 6- and 120-byte spans, including
enable's literal. Disable is 48 versus 52 bytes due to store merging. Step is
160 versus 156, consuming four following alignment bytes in the partial link
but still failing the complete function gate. Its wrapping step counter at
motor offset `0x60` is now named, with the prior layout alias preserved.

## Trigger-sync

`trsync.c/.h` supplies all eleven handlers, callbacks, dispatcher and tasks.
The 36-byte state holds two timers, report ticks at offset 24, a signal-list
pointer at 28 and flag/reason bytes at 32–34. Each eight-byte signal node
contains next and callback pointers, consistent with stepper's stop signal.
Actual wake storage is one byte at `0x24008b16`.

Six functions match exactly over 396 bytes: configuration, timeout setup,
signal insertion, OID lookup, report event and task. All eleven fit the link.
Dispatch/expiry/trigger/shutdown/start differences include paired loads/stores
and grouped reset bytes. A one-off 2,304-case ARM smoke comparison covered
all flag bytes and 0/1/3 callback chains across dispatch/expiry/report paths,
checking that each callback sees its node unlinked; callback/wake callees were
mocked. The retained reproducible gate is `check-gd-trsync.py`'s byte comparison.
