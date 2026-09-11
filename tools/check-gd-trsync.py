#!/usr/bin/env python3
"""mainBoardGD complete trigger-sync path, whole code/pool source gate."""
from gd_function_gate import main

UNITS = {'trsync': ('trsync.c', [])}
# Ranges end at the last instruction, excluding alignment before the next
# function. add_signal includes its 39-byte NUL-terminated inline string and
# one final alignment byte emitted within the function's literal-pool section.
CASES = [('command_config_trsync', 0xf78, 40),
         ('command_trsync_set_timeout', 0x1e38, 62),
         ('command_trsync_start', 0x1e78, 106),
         ('command_trsync_trigger', 0x1ee8, 152),
         ('trsync_add_signal', 0x58a8, 88),
         ('trsync_do_trigger', 0x5900, 76),
         ('trsync_expire_event', 0x5950, 68),
         ('trsync_oid_lookup', 0x5998, 12),
         ('trsync_report_event', 0x59a8, 40),
         ('trsync_shutdown', 0x59d0, 106),
         ('trsync_task', 0x5a40, 154)]
CASE_UNITS = {name: 'trsync' for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({
    'oid_alloc': 0x3f31, 'oid_lookup': 0x3fd9, 'oid_next': 0x4021,
    'irq_disable': 0x3881, 'irq_enable': 0x3889,
    'irq_save': 0x38a1, 'irq_restore': 0x3899,
    'sched_add_timer': 0x40a1, 'sched_del_timer': 0x41c1,
    'sched_shutdown': 0x4411, 'timer_read_time': 0x5581,
    'sched_wake_task': 0x44f1, 'sched_check_wake': 0x4161,
    'ctr_lookup_static_string': 0x2421, 'ctr_lookup_encoder': 0x21a1,
    'command_sendf': 0x1ca9, 'generated_string_00006c87': 0x6c87,
    'trsync_wake': 0x24008b16,
})

if __name__ == '__main__':
    raise SystemExit(main('trsync', CASES, UNITS, CASE_UNITS, SYMBOLS))
