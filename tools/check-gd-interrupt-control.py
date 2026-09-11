#!/usr/bin/env python3
"""GD32 interrupt control and system routing, full C code/pool extents."""
from gd_function_gate import main

UNITS = {'interrupt_control': ('interrupt_control.c', [])}
CASES = [('gd_motor_syscfg_route', 0x08002ed0, 58)]
CASE_UNITS = {name: 'interrupt_control' for name, _, _ in CASES}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('interrupt-control', CASES, UNITS, CASE_UNITS, SYMBOLS))
