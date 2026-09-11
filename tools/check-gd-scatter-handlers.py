#!/usr/bin/env python3
"""Full symbolic assembly spans from microlib's proven handlers.s member.

The runtime_scatter.c profile remains a separate semantic C reference.
These entries are runtime_assembly, never counted as recovered C bodies.
"""
from gd_function_gate import main

UNITS = {'scatter_handlers': ('scatter_handlers.S', [])}
CASES = [('gd_runtime_copy', 0x0800335a, 14),
         ('gd_runtime_zero', 0x0800336a, 14)]
CASE_UNITS = {name: 'scatter_handlers' for name, _, _ in CASES}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('scatter-handlers', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         span_kind='runtime_assembly'))
