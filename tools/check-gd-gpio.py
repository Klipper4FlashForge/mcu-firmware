#!/usr/bin/env python3
"""Check complete GPIO functions at stock execution addresses, including pools.

    python3 tools/check-gd-gpio.py --out work/mainBoardGD-gpio

The three source groups are isolated compilation units. External code/data
symbols bind to stock addresses; no stock opcode bytes are linked as input.
This is a function-level reconstruction gate, not a whole-firmware build.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('gd_gpio_clock_enable', 0x3080, 40, 'clock'),
    ('gpio_in_read', 0x30a8, 66, 'board'),
    ('gpio_peripheral', 0x37c8, 170, 'board'),
]
SYMBOLS = {'gd_gpio_clock_ids': 0x2400219c, 'gd_gpio_ports': 0x240021c4,
           'gd_motor_x': 0x2400282c, 'gd_motor_y': 0x24002514,
           'gd_motor_z': 0x24002b44, 'gd_gpio_clock_enable': 0x3081}
TARGET = ['--target=arm-none-eabi', '-mcpu=cortex-m7', '-mfpu=fpv5-d16',
          '-mfloat-abi=hard']
FLAGS = ['-O2', '-ffunction-sections', '-fdata-sections',
         '-mllvm', '-arm-promote-constant', '-fno-unroll-loops', '-falign-loops=4',
         '-mllvm', '-enable-shrink-wrap=false',
         '-fno-builtin',
         '-mllvm', '-align-all-functions=1',
         '-Wall', '-Wextra', '-Werror']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', type=Path, default=os.environ.get(
        'MCU_GD_CC', ROOT / 'work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--source', type=Path,
                        default=ROOT / 'mcu/mainBoardGD/recovered/gpio.c')
    parser.add_argument('--scheduler', help='global LLVM pre-RA scheduler experiment')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('gd_motor_check',
                                                ROOT / 'tools/check-gd-motor.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    if hashlib.md5(stock).hexdigest() != 'fb64911bac422a27d7ed7fab3597603f':
        parser.error('stock image is not the supported mainBoardGD version')
    scratch = tempfile.TemporaryDirectory(prefix='gd-gpio-') if not args.out else None
    out = args.out.resolve() if args.out else Path(scratch.name)
    out.mkdir(parents=True, exist_ok=True)
    cc = args.cc.resolve()
    flags = FLAGS + (['-mllvm', '-pre-RA-sched=' + args.scheduler] if args.scheduler else [])
    for group, define in [('vendor', 'GD_GPIO_VENDOR'), ('clock', 'GD_GPIO_CLOCK'),
                          ('board', None)]:
        subprocess.run([str(cc), *TARGET, *flags, *(['-D' + define] if define else []),
                        '-c', str(args.source.resolve()), '-o', str(out / (group + '.o'))],
                       check=True)
    rows = []
    for name, address, size, group in CASES:
        script = out / (name + '.ld')
        script.write_text('\n'.join(f'{symbol} = 0x{value:x};'
                                    for symbol, value in SYMBOLS.items() if symbol != name)
                          + f'\nSECTIONS {{ .text 0x{address:x} : {{ *(.text.{name}) }}\n'
                          + ' /DISCARD/ : { *(.text*) *(.ARM.exidx*) *(.ARM.extab*) } }\n')
        elf = out / (name + '.elf')
        subprocess.run([str(cc), *TARGET, '-nostdlib', '-Wl,--entry=' + name,
                        '-Wl,-T,' + str(script), str(out / (group + '.o')), '-o', str(elf)],
                       check=True)
        actual_address, candidate = helper.section(elf, '.text')
        if actual_address != address:
            raise ValueError('wrong linked address for ' + name)
        expected = stock[0x4418 + address:0x4418 + address + size]
        matched = sum(a == b for a, b in zip(expected, candidate))
        row = dict(name=name, address=address, expected_size=size,
                   actual_size=len(candidate), matching_bytes=matched,
                   expected_sha256=hashlib.sha256(expected).hexdigest(),
                   actual_sha256=hashlib.sha256(candidate).hexdigest(),
                   exact=candidate == expected)
        rows.append(row)
        print(f'{name:29s} {address:#010x} size={len(candidate)}/{size} '
              f'bytes={matched}/{size} {"EXACT" if row["exact"] else "DIFF"}')
    exact = [row for row in rows if row['exact']]
    report = dict(scope='isolated stock-address GPIO functions, not whole firmware',
                  stock_md5=hashlib.md5(stock).hexdigest(),
                  source_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in (args.source.resolve(),
                                              args.source.resolve().parent / 'gpio.h')},
                  compiler=str(cc), flags=TARGET + flags, results=rows,
                  exact_functions=len(exact), total_functions=len(rows),
                  exact_bytes=sum(row['expected_size'] for row in exact),
                  total_bytes=sum(row['expected_size'] for row in rows))
    if args.out:
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(exact)}/{len(rows)} exact functions; '
          f'{report["exact_bytes"]}/{report["total_bytes"]} bytes in exact functions.')
    if scratch:
        scratch.cleanup()
    return int(len(exact) != len(rows))


if __name__ == '__main__':
    raise SystemExit(main())
