#!/usr/bin/env python3
"""Typed timer channel register-offset array at its complete stock extent."""
from gd_function_gate import load, main

timer = load('check-gd-timer-vendor.py')
UNITS, CASES, CASE_UNITS = timer.DATA_UNITS, timer.DATA_CASES, timer.DATA_CASE_UNITS
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('timer-data', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='constant_data', extra_dependencies=[timer.__file__]))
