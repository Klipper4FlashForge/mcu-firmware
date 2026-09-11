#!/usr/bin/env python3
"""Full J-Scope setup function and embedded channel-name literal byte gate."""
from gd_function_gate import main

UNITS = {'debug_scope': ('debug_scope.c', []),
         'rtt_config': ('debug_scope.c', ['GD_RTT_CONFIG'])}
CASES = [('gd_jscope_init', 0x08000b38, 64),
         ('gd_rtt_config_up_buffer', 0x08000550, 204)]
CASE_UNITS = {'gd_jscope_init': 'debug_scope', 'gd_rtt_config_up_buffer': 'rtt_config'}
SYMBOLS = {'gd_jscope_buffer': 0x24002e8c,
           'gd_rtt_config_up_buffer': 0x08000551,
           'rcu_periph_clock_enable': 0x080028f1,
           'gd_rtt_control': 0x24003298, 'gd_rtt_down_buffer': 0x24003340,
           'gd_rtt_up_buffer': 0x24003350, 'gd_rtt_reverse_id': 0x08003378,
           'gd_rtt_terminal_name': 0x08003738, '__aeabi_memclr': 0x08000443}
DATA_UNITS = {'debug_scope_data': ('debug_scope.c', ['GD_DEBUG_SCOPE_DATA'])}
DATA_CASES = [('gd_rtt_reverse_id', 0x08003378, 16),
              ('gd_rtt_terminal_name', 0x08003738, 9)]
DATA_CASE_UNITS = {name: 'debug_scope_data' for name, _, _ in DATA_CASES}

if __name__ == '__main__':
    raise SystemExit(main('debug-scope', CASES, UNITS, CASE_UNITS, SYMBOLS))
