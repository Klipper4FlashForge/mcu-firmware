#!/usr/bin/env python3
"""Full GPIO output/motor pseudo-pin C bodies and input setup."""
from gd_function_gate import main

UNITS = {'gpio_input_setup': ('gpio_output.c', ['GD_GPIO_INPUT_SETUP']),
         'gpio_output_setup': ('gpio_output.c', ['GD_GPIO_OUTPUT_SETUP']),
         'gpio_output_reset': ('gpio_output.c', ['GD_GPIO_OUTPUT_RESET']),
         'gpio_output_toggle': ('gpio_output.c', ['GD_GPIO_OUTPUT_TOGGLE']),
         'gpio_output_write': ('gpio_output.c', [])}
CASES = [('gpio_in_setup', 0x30f0, 104), ('gpio_out_reset', 0x31b0, 264),
         ('gpio_out_setup', 0x32b8, 104), ('gpio_out_toggle_noirq', 0x3320, 266),
         ('gpio_out_write', 0x3430, 846)]
CASE_UNITS = dict(zip((c[0] for c in CASES), (
    'gpio_input_setup', 'gpio_output_reset', 'gpio_output_setup',
    'gpio_output_toggle', 'gpio_output_write')))
SYMBOLS = {'gd_gpio_ports': 0x240021c4, 'gd_gpio_clock_enable': 0x3081,
           'gpio_peripheral': 0x37c9, 'gpio_out_reset': 0x31b1,
           'irq_save': 0x38a1, 'irq_restore': 0x3899,
           'ctr_lookup_static_string': 0x2421, 'sched_shutdown': 0x4411,
           'mclib_gpio_direction': 0x5b9f, 'mclib_gpio_step': 0x5ba9,
           'mclib_gpio_disable': 0x5bb3, 'mclib_gpio_enable': 0x5bbd,
           'mclib_motor_y': 0x24002514, 'mclib_motor_x': 0x2400282c,
           'mclib_motor_z': 0x24002b44, 'mclib_motor_extruder': 0x240021ec,
           'gpio_step_inhibit_72': 0x24008b38, 'gpio_step_inhibit_73': 0x24008b39}

if __name__ == '__main__':
    raise SystemExit(main('gpio-output', CASES, UNITS, CASE_UNITS, SYMBOLS))
