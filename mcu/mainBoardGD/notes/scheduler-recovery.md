# Scheduler and move-queue recovery

Historical snapshot: the measurements below precede the queue-push,
statistics, move-reset and try-shutdown follow-ups. For current counts use
the [plan](../PLAN.md); subsequent evidence is in
[queue/button publication](queue-buttons-publication.md),
[statistics reloads](statistics-reload-recovery.md),
[move-reset shaping](move-reset-shaping.md),
[shutdown contract](shutdown-call-contract.md) and
[queue/OID searches](queue-oid-shaping.md).

Session: 2026-09-09. The current base-source gate verifies `sched_main`,
`sched_add_timer` and `sched_report_shutdown` exactly at their stock ITCM
addresses. This is source/function recovery with explicit external dependencies,
not proof that the partial image boots or that every callback is recovered.

## Sources, gates and measured extents

The source is split across `recovered/scheduler_main.c`, `scheduler_add.c`,
`scheduler_timers.c`, `scheduler_helpers.c`, `scheduler_shutdown.c`,
`move_queue.c/.h` and `statistics.c`. These are adaptations of the corresponding
Klipper scheduler/base-command behavior, with stock mainBoardGD's FlashForge
diagnostics. The levelBoard-specific eddy operations are not transplanted.

[`tools/check-gd-base.py`](../../../tools/check-gd-base.py) supplies addresses,
sizes and real C translation units to the shared full-section checker. The
current `work/mainBoardGD-base/results.json` contains 38/45 exact functions and
2,256 bytes in exact function spans; all recorded source hashes matched at this
review. Those spans can include local strings and alignment, not just opcodes.

| Newly exact function | ITCM address | Verified full span |
|---|---:|---:|
| `sched_main` | `0x4238` | 356 / 356 bytes |
| `sched_add_timer` | `0x40a0` | 192 / 192 bytes |
| `sched_report_shutdown` | `0x43a0` | 108 / 108 bytes |

The span accounting matters:

- `sched_main` has 304 instruction bytes through `0x4368`, followed by
  `"starting"` and `"shutdown clock=%u static_string_id=%hu"` and their local
  alignment. The full gate ends at `0x439c` exclusive.
- `sched_add_timer` has 176 instruction bytes through `0x4150`, followed by
  the 16-byte NUL-terminated `"Timer too close"` string. The gate ends at
  `0x4160` exclusive.
- `sched_report_shutdown` has 72 instruction bytes through `0x43e8`, followed
  by the **33-byte NUL-terminated** `"is_shutdown static_string_id=%hu"` and
  three alignment zeros. Its 108-byte gate ends at `0x440c` exclusive. Reporting
  this as 108 executable bytes would be incorrect.

Stock instructions and embedded strings can be checked in `work/itcm.lss` at
these addresses. The Ghidra export's smaller instruction-only function sizes
do not replace the full compiler-section comparison.

## Startup, tasks and shutdown

`sched_main` is a nonreturning entry into the cooperative task loop:

1. Call the actual init runner at `0x27c8`, then encode/send `starting`.
2. Disable interrupts and establish the shutdown continuation with `setjmp`
   using the context at RAM `0x240089f8`. The declaration is `returns_twice`;
   changing this compiler contract is not a harmless spelling change.
3. A nonzero return runs the shutdown sequence described below. Normal startup
   and shutdown continuation then enable interrupts and enter the task loop.
4. Poll interrupts, wait when no task was requested, set task state to running,
   invoke the task runner at `0x2810`, and call `stats_update(start, now)`.

The task-state byte at `0x2400328c` uses `0` for requested, `1` for running and
`-1` for idle. Before sleeping the loop rechecks the state with interrupts
disabled. `irq_wait` is the observed enable/nop/disable primitive, not a newly
invented WFI instruction. The subtraction/addition around the idle interval
adjusts the accounting start time so sleeping is excluded from task statistics.

The actual init order is allocation initialization, initial pins, timer-counter
initialization, the motor-init wrapper, then serial initialization. The generated
runner at `0x27c8` is authoritative; retained `.ctr` declaration order differs
and does not justify reordering it. The task runner calls trsync, analog input,
buttons, timer and console work, with `irq_poll` between them.

At `0x4410`, `sched_shutdown(reason)` disables interrupts and invokes `longjmp`
through the observed runtime veneer. Its complete 20-byte body is exact; the
runtime context layout and runtime implementation remain separate dependencies.
The shutdown continuation in `sched_main` then:

- Reads the current timer; records the reason only when not already shut down.
- Sets shutdown state at `0x24003290` to `2` while cleanup is in progress.
- Replaces user timer-list links with deleted/periodic/sentinel timers and kicks
  the timer at `0x5520`.
- Invokes `ctr_run_shutdownfuncs` at `0x27e8`: send-buffer shutdown, move reset,
  digital outputs, steppers, trsync, analog input, active IRQ clearing, timer reset.
- Sets shutdown state to `1`, enables interrupts, and sends FlashForge close
  diagnostics followed by `shutdown clock=%u static_string_id=%hu`.

`sched_report_shutdown` does not perform that cleanup or long jump. It sends
the same FlashForge diagnostics followed by `is_shutdown static_string_id=%hu`,
using the stored reason byte at `0x24003292`.

The three close-report values are `ff_timer_close` at `0x24008a98`,
`ff_close_num` at `0x24002e88`, and `ff_temp_waketime` at `0x24003294`. Their
encoder format is referenced by its already recovered string at ITCM `0x6d10`.
The source uses that symbol rather than allocating a new duplicate string.

## Timer callbacks and insertion

The common 12-byte timer ABI is `{ next pointer, callback pointer, waketime }`.
Initialized state in `recovered/state.c` defines timer-list pointers at
`0x24002188/0x2400218c`, deleted timer at `0x24002190`, periodic timer at
`0x24002e60`, sentinel at `0x24002e6c`, and wrap timer at `0x24002e78`.

`sched_add_timer(add, tag)` at `0x40a0` snapshots the waketime and enters an IRQ
critical section. Ordinary insertion walks the ordered linked list using the
wrap-aware comparison at `0x5518`. An earlier-than-head insertion first checks
against current time. If already late, it saves the attempted waketime, current
time and caller's tag into the three close-report globals, looks up
`"Timer too close"`, and calls `sched_shutdown` only if not already shut down.
It then uses the deleted-timer placeholder to install the new head and kicks
the timer. The normal return restores the caller's IRQ state.

Related verified source bodies include `sched_del_timer` at `0x41c0` (96 bytes)
and `sched_timer_dispatch` at `0x4440` (148 bytes). Dispatch invokes the callback,
or uses the fast stepper path when the callback field is the special null
marker. This convention applies to this field; it does not imply that ITCM
address zero is globally unusable as code. A done callback is removed; a
rescheduled callback is reinserted when its new deadline no longer precedes
the next timer. The cached last-insert pointer accelerates that search.

The periodic callback at `0x4060` advances its deadline by 100,000 microseconds,
wakes tasks and places the sentinel half a 32-bit timer range ahead. The deleted
callback at `0x2848` returns done. The sentinel callback at `0x4528` initiates
shutdown with `"sentinel timer called"`. These bodies and their initialized
callback pointers are separately verified.

Inlining boundaries are part of the observed layout. `run_shutdown` and
`report_close` are source helpers expanded into the containing functions; there
are no additional recovered out-of-line stock functions or separate coverage
credits for them. Timer-list reset is similarly present in the `sched_main`
shutdown body. The conditional shutdown check in `sched_add_timer` is local,
not a call to the still-mismatched standalone `sched_try_shutdown` body.

## Move storage and remaining mismatches

Moves use a singly linked free list and a FIFO head containing first/last
pointers. `move_alloc` disables interrupts while taking the free-list head and
shuts down on exhaustion. `move_free` and queue operations do not acquire
additional locks. Clearing/popping only updates the fields stock actually
touches: a stale last pointer when the queue becomes empty is not repaired by
invented writes, because insertion checks the first pointer before using it.

Six move helpers are exact: allocation (`0x3dd8`, 60 bytes), free (`0x3e18`, 16),
clear (`0x3e28`, 6), empty (`0x3e30`, 10), first (`0x3e40`, 4), and pop
(`0x3e48`, 10). The current source also reconstructs push, size setup and
free-list rebuilding, but their compiler output is not exact:

| Function | ITCM | Stock bytes | Candidate bytes | Equal positional bytes |
|---|---:|---:|---:|---:|
| `move_queue_push` | `0x3e58` | 40 | 30 | 1 |
| `move_queue_setup` | `0x3e80` | 84 | 84 | 82 |
| `move_reset` | `0x3ed8` | 86 | 88 | 43 |
| `stats_update` | `0x46c8` | 232 | 228 | 67 |

Setup records the largest requested stride before moves are allocated and
rejects the observed invalid-size/already-allocated conditions. Reset walks
the fixed-size allocation block to rebuild its free list. The current source
preserves the loop's base/stride snapshots and the distinct tail reloads;
that does not make its 88-byte result a match to the 86-byte target.

Statistics source maintains count, sum and scaled sum of squares with overflow
saturation, reports on the observed unsigned five-second elapsed-time test,
tracks timer wrapping, then clears the accumulators. It remains a nonexact
dependency of the exact `sched_main` body.

The same current base report also flags `oid_next` (53/58 equal bytes),
`sched_tasks_busy` (5/24, candidate 18 bytes), and `sched_try_shutdown` (0/20,
candidate 22 bytes). Do not describe the whole scheduler/base profile as exact
or hide these behind the three newly exact larger functions.

## Reproduce and interpret the result

```sh
python3 tools/check-gd-base.py
python3 tools/build-gd-partial.py
python3 tools/build-gd-scatter.py
```

The base command currently exits nonzero because of the seven explicit
mismatches above. Its JSON preserves per-function results and source/compiler
provenance. Partial linking connects available real source symbols and records
remaining external dependencies; it does not synthesize missing callback code.

The separate scatter artifact now verifies **3,284/3,284 bytes** at flash
`0x08003744..0x08004418`: three semantic scatter records, alignment and the exact
3,225-byte compression of source-built initialized RAM. See
[scatter-compression.md](scatter-compression.md). This solves a layout/data
dependency, not the runtime scatter helpers, ITCM payload, complete firmware
image or safe/bootable hardware operation. No flashing or bootability claim is
made by these source and byte-comparison gates.
