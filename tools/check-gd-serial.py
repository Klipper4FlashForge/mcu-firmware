#!/usr/bin/env python3
"""Compare complete reconstructed mainBoardGD serial functions with stock.

The gate links each function at its observed ITCM or flash address. External USART
vendor calls resolve to the observed ITCM veneers, not their flash bodies.
No stock executable code is included. This is not a whole-firmware link.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'mcu/mainBoardGD/recovered/serial.c'
CASES = [('USART0_IRQHandler', 0x220, 92), ('serial_enable_tx_irq', 0x4550, 24),
         ('serial_get_tx_byte', 0x4568, 52), ('serial_init', 0x45a0, 242),
         ('serial_rx_byte', 0x4698, 46),
         ('gd_usart_fifo_enable', 0x080030b8, 22)]
UNITS = {'serial': ('serial.c', []), 'serial_irq': ('serial_irq.c', []),
         'serial_vendor': ('serial_vendor.c', [])}
CASE_UNITS = {name: 'serial_vendor' if address >= 0x08000000 else
              'serial_irq' if name in ('serial_get_tx_byte', 'serial_rx_byte')
              else 'serial' for name, address, _ in CASES}
SYMBOLS = {
    'rcu_periph_clock_enable': 0x5b95,
    'gpio_af_set': 0x3011, 'gpio_mode_set': 0x3159,
    'gpio_output_options_set': 0x3781,
    'usart_deinit': 0x5c35, 'usart_baudrate_set': 0x5c3f,
    'usart_stop_bit_set': 0x5c49, 'usart_word_length_set': 0x5c53,
    'usart_parity_config': 0x5c5d, 'usart_hardware_flow_rts_config': 0x5c67,
    'usart_hardware_flow_cts_config': 0x5c71,
    'usart_receive_config': 0x5c7b, 'usart_transmit_config': 0x5c85,
    'usart_transmit_fifo_threshold_config': 0x5c8f,
    'usart_receive_fifo_threshold_config': 0x5c99,
    'gd_usart_fifo_enable': 0x5ca3, 'usart_enable': 0x5cad,
    'receive_buf': 0x24008870, 'receive_pos': 0x240089f0,
    'transmit_buf': 0x24008ab4, 'transmit_max': 0x24008b14, 'transmit_pos': 0x24008b15,
    'sched_wake_tasks': 0x4509, 'serial_rx_byte': 0x4699,
    'serial_get_tx_byte': 0x4569,
    'rcu_periph_reset_enable': 0x08002931,
    'rcu_periph_reset_disable': 0x08002911,
    'rcu_clock_freq_get': 0x08002159,
    'gd_rcu_apb_prescaler_shifts': 0x08003524,
}
FLAGS = ['--target=arm-none-eabi', '-mcpu=cortex-m7', '-mfpu=fpv5-d16',
         '-mfloat-abi=hard', '-O2', '-ffunction-sections', '-fdata-sections',
         '-mllvm', '-arm-promote-constant', '-fno-unroll-loops', '-falign-loops=4',
         '-mllvm', '-enable-shrink-wrap=false',
         '-fno-builtin',
         '-mllvm', '-align-all-functions=1',
         '-Wall', '-Wextra', '-Werror']


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-serial')
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--cflag', action='append', default=[])
    args = parser.parse_args()
    tc = load('gd_toolchain', ROOT / 'tools/check-gd-toolchain.py')
    helper = load('gd_motor', ROOT / 'tools/check-gd-motor.py')
    cc = tc.compiler_path(args.cc)
    stock = tc.STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != tc.STOCK_MD5:
        parser.error('unexpected stock image')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    commands = []
    for unit, (filename, defines) in UNITS.items():
        source = args.source.resolve() if unit == 'serial' else args.source.resolve().parent / filename
        command = [str(cc), *FLAGS, *args.cflag, *['-D' + d for d in defines], '-c', str(source),
                   '-o', str(out / (unit + '.o'))]
        subprocess.run(command, check=True)
        commands.append(command)
    rows = []
    for name, address, size in CASES:
        linker = out / (name + '.ld')
        linker.write_text('\n'.join('%s = 0x%x;' % (symbol, value)
                                    for symbol, value in SYMBOLS.items() if symbol != name)
                          + '\nSECTIONS { .text 0x%x : { *(.text.%s) }\n' % (address, name)
                          + ' /DISCARD/ : { *(.text*) *(.ARM.exidx*) *(.ARM.extab*) } }\n')
        elf = out / (name + '.elf')
        unit = CASE_UNITS[name]
        subprocess.run([str(cc), *FLAGS[:4], '-nostdlib', '-Wl,--entry=' + name,
                        '-Wl,-T,' + str(linker), str(out / (unit + '.o')), '-o', str(elf)], check=True)
        actual_address, actual = helper.section(elf, '.text')
        if actual_address != address:
            raise ValueError('wrong linked address')
        offset = address - 0x08000000 if address >= 0x08000000 else address + 0x4418
        expected = stock[offset:offset + size]
        if len(expected) != size:
            raise ValueError('stock function outside image')
        row = dict(name=name, address=address, expected_size=size, actual_size=len(actual),
                   matching_bytes=sum(a == b for a, b in zip(expected, actual)),
                   exact=expected == actual,
                   expected_sha256=hashlib.sha256(expected).hexdigest(),
                   actual_sha256=hashlib.sha256(actual).hexdigest())
        rows.append(row)
        print('%s: %s %d/%d bytes, size %d/%d' % (name, 'EXACT' if row['exact'] else 'DIFF',
              row['matching_bytes'], size, len(actual), size))
    exact = [row for row in rows if row['exact']]
    sources = [args.source.resolve(), args.source.resolve().parent / 'serial.h',
               args.source.resolve().parent / 'serial_irq.c',
               args.source.resolve().parent / 'serial_vendor.c',
               ROOT / 'mcu/mainBoardGD/recovered/gpio.h']
    report = dict(scope='isolated stock-address serial C functions; dependencies external',
                  stock_md5=tc.STOCK_MD5, image_sha256=hashlib.sha256(stock).hexdigest(),
                  compiler=str(cc), flags=FLAGS + args.cflag, commands=commands,
                  source_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sources}, results=rows,
                  exact_functions=len(exact), total_functions=len(rows),
                  exact_bytes=sum(row['expected_size'] for row in exact))
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('%d/%d exact functions; %d bytes in exact functions' %
          (len(exact), len(rows), report['exact_bytes']))
    return int(len(exact) != len(rows))


if __name__ == '__main__':
    raise SystemExit(main())
