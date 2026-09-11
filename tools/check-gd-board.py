#!/usr/bin/env python3
"""C board-main MPU/cache entry profile, distinct from architectural assembly."""
from gd_function_gate import main

UNITS = {'board_main': ('board_main.c', [])}
CASES = [('gd_board_main', 0x38b0, 298)]
CASE_UNITS = {'gd_board_main': 'board_main'}
SYMBOLS = {'mpu_region_struct_para_init': 0x5bc7,
           'mpu_region_config': 0x5bd1,
           'mpu_region_enable': 0x5bdb,
           'gd_jscope_init': 0x5be5, 'sched_main': 0x4239}

if __name__ == '__main__':
    raise SystemExit(main('board', CASES, UNITS, CASE_UNITS, SYMBOLS))
