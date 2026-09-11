#!/usr/bin/env python3
"""Full instruction/pool gates for mainBoardGD motor arithmetic helpers."""
from gd_function_gate import main

UNITS = {
    'math_leaf': ('mclib_math.c', []),
    'math_limit': ('mclib_math.c', ['MCLIB_MATH_LIMIT']),
    'math_observer': ('mclib_math.c', ['MCLIB_MATH_OBSERVER']),
}
CASES = [
    ('mclib_inverse_park', 0x08002950, 26),
    ('mclib_limit_dq_voltage', 0x080015e0, 144),
    ('mclib_observer_update', 0x08002c58, 276),
    ('mclib_sqrt_positive', 0x08002df8, 28),
]
CASE_UNITS = {
    'mclib_inverse_park': 'math_leaf',
    'mclib_sqrt_positive': 'math_leaf',
    'mclib_limit_dq_voltage': 'math_limit',
    'mclib_observer_update': 'math_observer',
}
SYMBOLS = {
    'mclib_sqrt_positive': 0x08002df9,
    'mclib_atan2': 0x08000891,
    'mclib_observer_velocity_update': 0x08002d71,
    'mclib_wrap_angle': 0x08000849,
}

if __name__ == '__main__':
    raise SystemExit(main('math', CASES, UNITS, CASE_UNITS, SYMBOLS))
