#!/usr/bin/env python3
"""mainBoardGD DMA interrupt flag/status helpers, complete code/pool gate."""
from gd_function_gate import main

# Retired 2026-09-11: these spans are GigaDevice's SDK (check-gd-sdk.py).
UNITS = {}
CASES = []
CASE_UNITS = {name: 'dma_interrupts' for name, _, _ in CASES}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('dma-irqs', CASES, UNITS, CASE_UNITS, SYMBOLS))
