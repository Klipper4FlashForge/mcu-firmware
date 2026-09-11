#!/usr/bin/env python3
"""mainBoardGD analog input commands and GPIO ADC, complete code/pool gate."""
from gd_function_gate import main

UNITS = {'analog_in': ('analog_in.c', []),
         'analog_gpio': ('analog_in.c', ['GD_ANALOG_GPIO_IMPLEMENTATION']),
         'analog_delay': ('analog_in.c', ['GD_ANALOG_GPIO_IMPLEMENTATION', 'GD_ANALOG_DELAY'])}
CASES = [('analog_in_event', 0x7c0, 168),
         ('analog_in_shutdown', 0x868, 102),
         ('analog_in_task', 0x8d0, 196),
         ('command_config_analog_in', 0xd18, 58),
         ('command_query_analog_in', 0x1a28, 92),
         ('gpio_adc_cancel_sample', 0x2e98, 58),
         ('gpio_adc_read', 0x2ed8, 28),
         ('gpio_adc_sample', 0x2ef8, 54),
         ('gpio_adc_setup', 0x2f30, 220), ('gd_delay_us', 0x5ae0, 60)]
CASE_UNITS = {name: 'analog_delay' if name == 'gd_delay_us' else
              'analog_gpio' if name.startswith('gpio_adc_') else 'analog_in'
              for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({'oid_alloc': 0x3f31, 'oid_lookup': 0x3fd9, 'oid_next': 0x4021,
    'irq_disable': 0x3881, 'irq_enable': 0x3889, 'irq_save': 0x38a1, 'irq_restore': 0x3899,
    'sched_add_timer': 0x40a1, 'sched_del_timer': 0x41c1,
    'sched_check_wake': 0x4161, 'sched_wake_task': 0x44f1,
    'sched_try_shutdown': 0x44d9, 'sched_shutdown': 0x4411,
    'ctr_lookup_encoder': 0x21a1, 'ctr_lookup_static_string': 0x2421,
    'command_sendf': 0x1ca9, 'timer_from_us': 0x5131,
    'gpio_peripheral': 0x37c9, 'gd_delay_us': 0x5ae1,
    'rcu_periph_clock_enable': 0x5b95,
    'adc_deinit': 0x391, 'adc_clock_config': 0x349,
    'adc_channel_length_config': 0x301,
    'analog_wake': 0x24003814, 'gpio_adc_channel_samples': 0x24008b18})

if __name__ == '__main__':
    raise SystemExit(main('analog-in', CASES, UNITS, CASE_UNITS, SYMBOLS))
