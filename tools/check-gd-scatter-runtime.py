#!/usr/bin/env python3
"""Compare complete C scatter helper bodies at stock execution addresses."""
from gd_function_gate import main

UNITS = {'scatter_decompress': ('runtime_scatter.c', []),
         'scatter_copy': ('runtime_scatter.c', ['GD_SCATTER_COPY']),
         'scatter_null': ('runtime_scatter.c', ['GD_SCATTER_NULL']),
         'scatter_zero': ('runtime_scatter.c', ['GD_SCATTER_ZERO'])}
CASES = [('gd_runtime_decompress', 0x080004ec, 94),
         ('gd_runtime_copy', 0x0800335a, 14),
         ('gd_runtime_null', 0x08003368, 2),
         ('gd_runtime_zero', 0x0800336a, 14)]
CASE_UNITS = {'gd_runtime_decompress': 'scatter_decompress',
              'gd_runtime_copy': 'scatter_copy',
              'gd_runtime_null': 'scatter_null',
              'gd_runtime_zero': 'scatter_zero'}
SYMBOLS = {}
SEMANTIC_REFERENCES = {'gd_runtime_copy', 'gd_runtime_zero'}

if __name__ == '__main__':
    raise SystemExit(main('scatter-runtime', CASES, UNITS, CASE_UNITS, SYMBOLS,
                         semantic_references=SEMANTIC_REFERENCES))
