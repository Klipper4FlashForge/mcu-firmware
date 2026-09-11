#!/usr/bin/env python3
"""Complete mainBoardGD angle functions, with full literal-pool comparison."""
from gd_function_gate import main

UNITS = {'angles': ('mclib_angles.c', []),
         'atan': ('mclib_angles.c', ['GD_ANGLE_ATAN'])}
CASES = [('mclib_wrap_angle', 0x08000848, 72),
         ('mclib_atan2', 0x08000890, 640),
         ('mclib_observer_velocity_update', 0x08002d70, 136)]
CASE_UNITS = {name: 'atan' if name == 'mclib_atan2' else 'angles'
              for name, _, _ in CASES}
SYMBOLS = {'mclib_atan_table': 0x0800338c}
DATA_UNITS = {'angle_tables': ('mclib_angles.c', ['GD_ANGLE_TABLES'])}
DATA_CASES = [('mclib_atan_table', 0x0800338c, 408)]
DATA_CASE_UNITS = {'mclib_atan_table': 'angle_tables'}

if __name__ == '__main__':
    raise SystemExit(main('angles', CASES, UNITS, CASE_UNITS, SYMBOLS))
