#!/usr/bin/env python3
"""Typed numeric atan table, with complete stock-address object comparison."""
from gd_function_gate import load, main

angles = load('check-gd-angles.py')
UNITS = angles.DATA_UNITS
CASES = angles.DATA_CASES
CASE_UNITS = angles.DATA_CASE_UNITS
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('angle-data', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='constant_data', extra_dependencies=[angles.__file__]))
