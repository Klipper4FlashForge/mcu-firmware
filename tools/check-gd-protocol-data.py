#!/usr/bin/env python3
"""Compile the retained ACK encoder and parser-error literal as typed data."""
from gd_function_gate import main

UNITS = {'protocol_data': ('protocol_data.c', [])}
CASES = [('encode_acknak', 0x68e8, 8),
         ('generated_string_00006dc2', 0x6dc2, 21)]
CASE_UNITS = {name: 'protocol_data' for name, _, _ in CASES}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('protocol-data', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='constant_data'))
