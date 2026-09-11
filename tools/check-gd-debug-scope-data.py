#!/usr/bin/env python3
"""Exact constant objects used by mainBoardGD RTT initialization."""
from gd_function_gate import load, main

scope = load('check-gd-debug-scope.py')
UNITS, CASES, CASE_UNITS = scope.DATA_UNITS, scope.DATA_CASES, scope.DATA_CASE_UNITS
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('debug-scope-data', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='constant_data', extra_dependencies=[scope.__file__]))
