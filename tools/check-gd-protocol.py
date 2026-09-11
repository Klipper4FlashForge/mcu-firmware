#!/usr/bin/env python3
"""mainBoardGD protocol/console full-function C source profile."""
from gd_function_gate import main

UNITS = {'command_protocol': ('command_protocol.c', []),
         'command_console': ('command_protocol.c', ['GD_PROTOCOL_CONSOLE']),
         'command_crc': ('command_protocol.c', ['GD_PROTOCOL_CRC'])}
CASES = [('command_dispatch', 0x1070, 332),
         ('command_encode_and_frame', 0x11e0, 380),
         ('command_find_block', 0x15a8, 232),
         ('command_send_ack', 0x1c98, 12),
         ('command_sendf', 0x1ca8, 52),
         ('console_sendf', 0x2050, 130), ('console_task', 0x20d8, 134),
         ('crc16_ccitt', 0x2160, 60), ('sendf_shutdown', 0x4518, 14)]
CASE_UNITS = {name: 'command_console' if name.startswith('console_') else
              'command_crc' if name == 'crc16_ccitt' else 'command_protocol'
              for name, _, _ in CASES}
SYMBOLS = {
    'command_index': 0x6560, 'command_index_size': 0x6880,
    'encode_acknak': 0x68e8, 'generated_string_00006dc2': 0x6dc2,
    'next_sequence': 0x24002e5c, 'command_sync_state': 0x24003816,
    'in_sendf': 0x2400881c, 'ctr_lookup_static_string': 0x2421,
    'sched_shutdown': 0x4411, 'sched_is_shutdown': 0x4221,
    'sched_report_shutdown': 0x43a1, 'irq_poll': 0x3891,
    'crc16_ccitt': 0x2161, 'console_sendf': 0x2051, 'command_sendf': 0x1ca9,
    'command_encode_and_frame': 0x11e1, 'command_find_block': 0x15a9,
    'command_dispatch': 0x1071, 'command_send_ack': 0x1c99,
    'memchr': 0x5b59, '__aeabi_memcpy': 0x5b4f, 'memcpy': 0x5b4f,
    'memmove': 0x5b81, '__aeabi_memmove': 0x5b81,
    'transmit_buf': 0x24008ab4, 'transmit_pos': 0x24008b15,
    'transmit_max': 0x24008b14, 'receive_buf': 0x24008870,
    'receive_pos': 0x240089f0, 'serial_enable_tx_irq': 0x4551,
    'sched_wake_tasks': 0x4509, 'irq_save': 0x38a1, 'irq_restore': 0x3899,
}

if __name__ == '__main__':
    raise SystemExit(main('protocol', CASES, UNITS, CASE_UNITS, SYMBOLS))
