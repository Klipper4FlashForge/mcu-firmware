#!/usr/bin/env python3
"""Complete configuration-finalization command, including both string pools."""
from gd_function_gate import main

UNITS = {'config_finalize': ('config_finalize.c', [])}
CASES = [('command_finalize_config', 0x1460, 324)]
CASE_UNITS = {'command_finalize_config': 'config_finalize'}
SYMBOLS = {'alloc_end': 0x24003810, 'config_crc': 0x24003818,
           'move_count': 0x2400881e, 'move_free_list': 0x24008820,
           'move_item_size': 0x24008824, 'move_list': 0x24008828,
           'dynmem_end': 0x2d79, 'generated_string_0000692a': 0x692a,
           'ctr_lookup_static_string': 0x2421, 'sched_shutdown': 0x4411,
           '__aeabi_memclr': 0x5b45}

if __name__ == '__main__':
    raise SystemExit(main('config-finalize', CASES, UNITS, CASE_UNITS, SYMBOLS))
