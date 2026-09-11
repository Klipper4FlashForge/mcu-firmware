#!/usr/bin/env python3
"""Architectural startup/context assembly profile; not C-function recovery."""
from gd_function_gate import main

UNITS = {'startup_runtime': ('startup_runtime.S', [])}
CASES = [('gd_runtime_entry', 0x080003a4, 20),
         ('Reset_Handler', 0x080003b8, 60),
         ('gd_runtime_setjmp', 0x08000488, 26),
         ('gd_runtime_longjmp', 0x080004a2, 36),
         ('gd_scatter_dispatch', 0x080004c8, 36),
         ('clear_active_irq', 0x00000b10, 30)]
CASE_UNITS = {name: 'startup_runtime' for name, _, _ in CASES}
EXTRA_FUNCTIONS = {0x080003ac: 'gd_runtime_after_scatter',
                   0x080003e4: 'Default_Handler'}
SYMBOLS = {'gd_runtime_entry': 0x080003a5, 'gd_runtime_after_scatter': 0x080003ad,
           'gd_scatter_dispatch': 0x080004c9, 'SystemInit': 0x08000621,
           'gd_board_main': 0x38b1, 'gd_initial_sp': 0x2400b340,
           'gd_boot_ram_base': 0x24000000, 'gd_scatter_table': 0x08003744,
           'gd_scatter_table_end': 0x08003774}

if __name__ == '__main__':
    raise SystemExit(main('runtime', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='runtime_assembly'))
