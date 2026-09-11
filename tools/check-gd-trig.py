#!/usr/bin/env python3
"""Stock-address full code/pool gates for mainBoardGD lookup trigonometry."""
from gd_function_gate import main

UNITS = {'sincos': ('mclib_trig.c', []),
         'sine': ('mclib_trig.c', ['GD_TRIG_SINE'])}
CASES = [('mclib_sincos', 0x08002970, 480),
         ('mclib_sine', 0x08002b50, 248)]
CASE_UNITS = {'mclib_sincos': 'sincos', 'mclib_sine': 'sine'}
SYMBOLS = {'mclib_sine_table': 0x0800352c}
DATA_UNITS = {'trig_tables': ('mclib_trig.c', ['GD_TRIG_TABLES'])}
DATA_CASES = [('mclib_sine_table', 0x0800352c, 524)]
DATA_CASE_UNITS = {'mclib_sine_table': 'trig_tables'}

if __name__ == '__main__':
    raise SystemExit(main('trig', CASES, UNITS, CASE_UNITS, SYMBOLS))
