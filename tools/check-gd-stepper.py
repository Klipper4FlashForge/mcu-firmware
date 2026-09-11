#!/usr/bin/env python3
"""mainBoardGD double-scheduled stepper path, whole code/pool source gate."""
from gd_function_gate import main

UNITS = {'stepper': ('stepper.c', []),
         'stepper_entry': ('stepper.c', ['GD_STEPPER_ENTRY']),
         'stepper_load': ('stepper.c', ['GD_STEPPER_LOAD']),
         'stepper_stop': ('stepper.c', ['GD_STEPPER_STOP'])}
CASES = [('command_config_stepper', 0xf08, 106),
         ('command_queue_step', 0x1b58, 188),
         ('command_reset_step_clock', 0x1c28, 108),
         ('command_set_next_step_dir', 0x1d70, 56),
         ('command_stepper_get_position', 0x1da8, 96),
         ('command_stepper_stop_on_trigger', 0x1e08, 48),
         ('stepper_event', 0x47b0, 4), ('stepper_event_full', 0x47b8, 152),
         ('stepper_load_next', 0x4850, 96), ('stepper_shutdown', 0x48b0, 80),
         ('stepper_stop', 0x4900, 126)]
CASE_UNITS = {name: 'stepper_entry' if name == 'stepper_event' else
              'stepper_load' if name == 'stepper_load_next' else
              'stepper_stop' if name == 'stepper_stop' else 'stepper'
              for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({
    'oid_alloc': 0x3f31, 'oid_lookup': 0x3fd9, 'oid_next': 0x4021,
    'move_alloc': 0x3dd9, 'move_free': 0x3e19, 'move_queue_clear': 0x3e29,
    'move_queue_empty': 0x3e31, 'move_queue_pop': 0x3e49,
    'move_queue_push': 0x3e59, 'move_queue_setup': 0x3e81,
    'irq_disable': 0x3881, 'irq_enable': 0x3889,
    'sched_add_timer': 0x40a1, 'sched_del_timer': 0x41c1,
    'sched_shutdown': 0x4411, 'timer_read_time': 0x5581,
    'timer_from_us': 0x5131, 'timer_is_before': 0x5519,
    'gpio_out_setup': 0x32b9, 'gpio_out_toggle_noirq': 0x3321,
    'gpio_out_write': 0x3431, 'ctr_lookup_static_string': 0x2421,
    'ctr_lookup_encoder': 0x21a1, 'command_sendf': 0x1ca9,
    'trsync_oid_lookup': 0x5999, 'trsync_add_signal': 0x58a9,
})

if __name__ == '__main__':
    raise SystemExit(main('stepper', CASES, UNITS, CASE_UNITS, SYMBOLS))
