#!/usr/bin/env python3
"""mainBoardGD button debouncing/report commands, complete code/pool gate."""
from gd_function_gate import main

UNITS = {'buttons': ('buttons.c', [])}
CASES = [('buttons_event', 0x998, 186), ('buttons_task', 0xa58, 180),
         ('command_buttons_ack', 0xbb8, 104), ('command_buttons_add', 0xc20, 112),
         ('command_buttons_query', 0xc90, 124), ('command_config_buttons', 0xd58, 76)]
CASE_UNITS = {name: 'buttons' for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({'oid_alloc': 0x3f31, 'oid_lookup': 0x3fd9, 'oid_next': 0x4021,
    'gpio_in_setup': 0x30f1, 'gpio_in_read': 0x30a9,
    'irq_disable': 0x3881, 'irq_enable': 0x3889,
    'sched_add_timer': 0x40a1, 'sched_del_timer': 0x41c1,
    'sched_check_wake': 0x4161, 'sched_wake_task': 0x44f1,
    'sched_shutdown': 0x4411, 'ctr_lookup_static_string': 0x2421,
    'ctr_lookup_encoder': 0x21a1, 'command_sendf': 0x1ca9,
    'buttons_wake': 0x24003815})

if __name__ == '__main__':
    raise SystemExit(main('buttons', CASES, UNITS, CASE_UNITS, SYMBOLS))
