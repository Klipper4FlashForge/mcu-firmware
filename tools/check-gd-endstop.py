#!/usr/bin/env python3
"""mainBoardGD endstop homing and oversampling, complete code/pool gate."""
from gd_function_gate import main

UNITS = {'endstop': ('endstop.c', [])}
CASES = [('command_config_endstop', 0xe08, 50),
         ('command_endstop_home', 0x1360, 110),
         # 82-byte code, 2-byte NOP, 58-byte string including NUL, 2 pad.
         ('command_endstop_query_state', 0x13d0, 144),
         ('endstop_event', 0x2d98, 146),
         ('endstop_oversample_event', 0x2e30, 100)]
CASE_UNITS = {name: 'endstop' for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({'oid_alloc': 0x3f31, 'oid_lookup': 0x3fd9,
                'gpio_in_setup': 0x30f1, 'gpio_in_read': 0x30a9,
                'irq_disable': 0x3881, 'irq_enable': 0x3889,
                'sched_add_timer': 0x40a1, 'sched_del_timer': 0x41c1,
                'trsync_oid_lookup': 0x5999, 'trsync_do_trigger': 0x5901,
                'ctr_lookup_encoder': 0x21a1, 'command_sendf': 0x1ca9})

if __name__ == '__main__':
    raise SystemExit(main('endstop', CASES, UNITS, CASE_UNITS, SYMBOLS))
