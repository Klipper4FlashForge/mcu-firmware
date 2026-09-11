#!/usr/bin/env python3
"""mainBoardGD MPU region helpers: complete instruction sections, no blobs.

The following stock ranges contain no literal pools. Zero gaps before the
next functions are linker alignment, not bytes in these function sections.
"""
from gd_function_gate import main

# Retired 2026-09-11: the MPU helpers are gd32h7xx_misc.c (check-gd-sdk.py).
UNITS = {}
CASES = []
CASE_UNITS = {name: 'mpu' for name, _, _ in CASES}
SYMBOLS = {}

if __name__ == '__main__':
    raise SystemExit(main('mpu', CASES, UNITS, CASE_UNITS, SYMBOLS))
