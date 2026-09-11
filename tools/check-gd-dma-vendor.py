#!/usr/bin/env python3
"""Complete DMA SDK C spans, excluding already recovered IRQ helpers."""
from gd_function_gate import main

# Retired 2026-09-11: every span is GigaDevice's gd32h7xx_dma.c (check-gd-sdk.py).
UNITS = {}
CASES = []
CASE_UNITS = {name: 'dma_init' if name == 'dma_single_data_mode_init' else 'dma_vendor'
              for name, _, _ in CASES}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('dma-vendor', CASES, UNITS, CASE_UNITS, SYMBOLS))
