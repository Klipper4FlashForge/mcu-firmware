#!/usr/bin/env python3
"""Independent compiled-object check for the shared APB prescaler table."""
from gd_function_gate import main

UNITS = {'clock_tables': ('clock_tables.c', [])}
CASES = [('gd_rcu_apb_prescaler_shifts', 0x08003524, 8)]
CASE_UNITS = {'gd_rcu_apb_prescaler_shifts': 'clock_tables'}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('platform-data', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='constant_data'))
