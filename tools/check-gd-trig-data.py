#!/usr/bin/env python3
"""Full byte gate for the typed, guarded quarter-wave sine table."""
from gd_function_gate import load, main

trig = load('check-gd-trig.py')
UNITS = trig.DATA_UNITS
CASES = trig.DATA_CASES
CASE_UNITS = trig.DATA_CASE_UNITS
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('trig-data', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='constant_data', extra_dependencies=[trig.__file__]))
