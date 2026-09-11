#!/usr/bin/env python3
"""mainBoardGD queued digital outputs/software PWM, full code/pool gate."""
from gd_function_gate import main

UNITS = {'digital_out': ('digital_out.c', []),
         'digital_queue_entry': ('digital_out.c', ['GD_DIGITAL_QUEUE_ENTRY'])}
CASES = [('command_config_digital_out', 0xda8, 90),
         ('command_queue_digital_out', 0x1a88, 56),
         ('command_queue_digital_out_impl', 0x1ac0, 146),
         ('command_set_digital_out', 0x1ce0, 18),
         ('command_set_digital_out_pwm_cycle', 0x1cf8, 116),
         ('command_update_digital_out', 0x1f80, 204),
         ('digital_load_event', 0x2850, 312),
         ('digital_out_shutdown', 0x2988, 102),
         ('digital_toggle_event', 0x29f0, 76)]
CASE_UNITS = {name: 'digital_queue_entry' if name == 'command_queue_digital_out'
              else 'digital_out' for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({'oid_alloc': 0x3f31, 'oid_lookup': 0x3fd9, 'oid_next': 0x4021,
    'move_alloc': 0x3dd9, 'move_free': 0x3e19, 'move_queue_clear': 0x3e29,
    'move_queue_empty': 0x3e31, 'move_queue_first': 0x3e41, 'move_queue_pop': 0x3e49,
    'move_queue_push': 0x3e59, 'move_queue_setup': 0x3e81,
    'gpio_out_setup': 0x32b9, 'gpio_out_toggle_noirq': 0x3321, 'gpio_out_write': 0x3431,
    'irq_disable': 0x3881, 'irq_enable': 0x3889,
    'sched_add_timer': 0x40a1, 'sched_del_timer': 0x41c1,
    'timer_read_time': 0x5581, 'timer_from_us': 0x5131, 'timer_is_before': 0x5519,
    'ctr_lookup_static_string': 0x2421, 'sched_shutdown': 0x4411,
    'generated_string_00006ad5': 0x6ad5})

if __name__ == '__main__':
    raise SystemExit(main('digital-out', CASES, UNITS, CASE_UNITS, SYMBOLS))
