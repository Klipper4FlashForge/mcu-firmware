#!/usr/bin/env python3
"""Compile typed mainBoardGD initial state and compare all object bytes in RAM.

    python3 tools/check-gd-state.py --out work/mainBoardGD-state

This verifies source initializers against the stock scatter-decompressed data,
including zero fields and padding. Dependencies resolve to explicit symbols;
no stock byte arrays or opcodes are used as candidate linker input. CASES and
SYMBOLS are also the machine-readable placement map for partial integration.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

from scatterload import decompress, entries

ROOT = Path(__file__).resolve().parents[1]
RAM = 0x24000000
COMPATIBILITY_FLAGS = ['-mllvm', '-arm-promote-constant', '-fno-unroll-loops',
                       '-falign-loops=4', '-mllvm', '-enable-shrink-wrap=false', '-fno-builtin',
                       '-mllvm', '-align-all-functions=1']
CASES = [
    ('mclib_adc_dma_y', 0x24000000, 8),
    ('mclib_adc_dma_z', 0x24000008, 8),
    ('sched_timer_list', 0x24002188, 4),
    ('sched_last_insert', 0x2400218c, 4),
    ('deleted_timer', 0x24002190, 12),
    ('gd_gpio_clock_ids', 0x2400219c, 40),
    ('gd_gpio_ports', 0x240021c4, 40),
    ('mclib_motor_extruder', 0x240021ec, 0x318),
    ('mclib_motors', 0x24002504, 16),
    ('mclib_motor_y', 0x24002514, 0x318),
    ('mclib_motor_x', 0x2400282c, 0x318),
    ('mclib_motor_z', 0x24002b44, 0x318),
    ('next_sequence', 0x24002e5c, 1),
    ('periodic_timer', 0x24002e60, 12),
    ('sentinel_timer', 0x24002e6c, 12),
    ('wrap_timer', 0x24002e78, 12),
]
# Layout, not fabricated C objects. The final four bytes' original ownership
# cannot be proved from absence of references; retain that inference explicitly.
ALIGNMENT_GAPS = [
    dict(name='next_sequence_alignment', address=0x24002e5d, size=3, alignment=4,
         evidence='byte next_sequence ends at 0x24002e5d; pointer-containing '
                  'periodic_timer requires word alignment at 0x24002e60',
         provenance='natural_alignment'),
    dict(name='initialized_ram_end_alignment', address=0x24002e84, size=4, alignment=8,
         evidence='12-byte wrap_timer ends at 0x24002e84; stock scatter table '
                  'ends expanded RW and starts ZI at 8-byte-aligned 0x24002e88; '
                  'no immediate or literal references to these four bytes found',
         provenance='inferred_boundary_alignment_not_proof_of_no_unused_object'),
]
SYMBOLS = {
    'gd_gpio_port_a': 0x58020000, 'gd_gpio_port_b': 0x58020400,
    'gd_gpio_port_c': 0x58020800, 'gd_gpio_port_d': 0x58020c00,
    'gd_gpio_port_e': 0x58021000, 'gd_gpio_port_f': 0x58021400,
    'gd_gpio_port_g': 0x58021800, 'gd_gpio_port_h': 0x58021c00,
    'gd_gpio_port_j': 0x58022400,
    'mclib_acquisition_extruder': 0x24003750, 'mclib_acquisition_y': 0x24003780,
    'mclib_acquisition_x': 0x240037b0, 'mclib_acquisition_z': 0x240037e0,
    'mclib_pwm_extruder': 0x24008840, 'mclib_pwm_y': 0x2400884c,
    'mclib_pwm_x': 0x24008858, 'mclib_pwm_z': 0x24008864,
    'timer_wrap_event': 0x5899,
    'deleted_event': 0x2849, 'periodic_event': 0x4061, 'sentinel_event': 0x4529,
}
ALIASES = {'gd_motor_x': 'mclib_motor_x', 'gd_motor_y': 'mclib_motor_y',
           'gd_motor_z': 'mclib_motor_z'}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('MCU_GD_CC'))
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-state')
    args = parser.parse_args()
    tc = module('gd_toolchain', ROOT / 'tools/check-gd-toolchain.py')
    motor = module('gd_motor', ROOT / 'tools/check-gd-motor.py')
    cc, out = tc.compiler_path(args.cc), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stock = tc.STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != tc.STOCK_MD5:
        raise ValueError('unsupported mainBoardGD stock image')
    regions = list(entries(stock, 0x08000000, 0x3744))
    records = [r for r in regions if r[1] == RAM]
    if len(records) != 1 or records[0][2:] != (11912, 0x080004ec):
        raise ValueError('unexpected initialized RAM scatter record')
    source_address, _, size, _ = records[0]
    data, compressed_size = decompress(stock[source_address - 0x08000000:], size)
    if len(data) != size:
        raise ValueError('wrong expanded RAM size')
    source = ROOT / 'mcu/mainBoardGD/recovered/state.c'
    obj, elf, script = out / 'state.o', out / 'state.elf', out / 'state.ld'
    flags = [*tc.FLAGS, *COMPATIBILITY_FLAGS]
    command = [str(cc), *flags, '-c', str(source), '-o', str(obj)]
    subprocess.run(command, check=True)
    definitions = '\n'.join(f'{name} = 0x{address:x};' for name, address in SYMBOLS.items())
    placements = '\n'.join(
        f'  .state_{name} 0x{address:x} : {{ *(.data.{name}) *(.rodata.{name}) *(.bss.{name}) }}'
        for name, address, _ in CASES)
    layout = '\n'.join(
        f'  .alignment_{gap["name"]} 0x{gap["address"]:x} : '
        f'{{ FILL(0); BYTE(0); . = ALIGN({gap["alignment"]}); }}'
        for gap in ALIGNMENT_GAPS)
    script.write_text(definitions + '\nSECTIONS {\n' + placements
                      + '\n' + layout
                      + '\n /DISCARD/ : { *(.text*) *(.ARM.exidx*) *(.ARM.extab*) }\n}\n')
    link_command = [str(cc), *tc.FLAGS[:4], '-nostdlib', '-Wl,--entry=wrap_timer',
                    '-Wl,-T,' + str(script), str(obj), '-o', str(elf)]
    subprocess.run(link_command, check=True)
    rows = []
    for name, address, size in CASES:
        actual_address, candidate = motor.section(elf, '.state_' + name)
        expected = data[address - RAM:address - RAM + size]
        if actual_address != address or len(expected) != size:
            raise ValueError('state address/range mismatch: ' + name)
        exact = candidate == expected
        matched = sum(a == b for a, b in zip(candidate, expected))
        rows.append(dict(name=name, kind='initialized_data', origin='typed_initializer', address=address,
                         expected_size=size, actual_size=len(candidate), exact=exact,
                         matching_bytes=matched, expected_sha256=hashlib.sha256(expected).hexdigest(),
                         actual_sha256=hashlib.sha256(candidate).hexdigest()))
        print(f'{name:24s} {address:#010x} {matched}/{size} bytes '
              f'size={len(candidate)} {"EXACT" if exact else "DIFF"}')
    for gap in ALIGNMENT_GAPS:
        address, size = gap['address'], gap['size']
        actual_address, candidate = motor.section(elf, '.alignment_' + gap['name'])
        expected = data[address - RAM:address - RAM + size]
        if actual_address != address or expected != bytes(size):
            raise ValueError('unexpected nonzero or misplaced alignment gap: ' + gap['name'])
        exact = candidate == expected
        rows.append(dict(name=gap['name'], kind='initialized_data', origin='linker_alignment',
                         address=address, expected_size=size, actual_size=len(candidate),
                         exact=exact, matching_bytes=sum(a == b for a, b in zip(candidate, expected)),
                         expected_sha256=hashlib.sha256(expected).hexdigest(),
                         actual_sha256=hashlib.sha256(candidate).hexdigest(),
                         evidence=gap['evidence'], provenance=gap['provenance']))
        print(f'{gap["name"]:32s} {size} linker alignment bytes {"EXACT" if exact else "DIFF"}')
    nm = cc.parent / 'llvm-nm'
    symbols = {}
    for line in subprocess.check_output([str(nm), '--defined-only', str(elf)], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    alias_checks = {name: symbols.get(name) == symbols.get(target)
                    and symbols.get(target) == dict((n, a) for n, a, _ in CASES)[target]
                    for name, target in ALIASES.items()}
    if not all(alias_checks.values()):
        raise ValueError('GPIO views do not alias the physical motor objects')
    inputs = [source, source.with_suffix('.h'), source.parent / 'gpio.h',
              source.parent / 'mclib_state.h', Path(__file__).resolve(),
              ROOT / 'tools/check-gd-toolchain.py', ROOT / 'tools/check-gd-motor.py',
              ROOT / 'tools/scatterload.py']
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in inputs}
    report = dict(scope='typed initialized RAM objects; not compressed image or full firmware',
                  stock_md5=tc.STOCK_MD5, image_sha256=hashlib.sha256(stock).hexdigest(),
                  expanded_ram=dict(address=RAM, size=len(data), compressed_size=compressed_size,
                                    sha256=hashlib.sha256(data).hexdigest()),
                  source_sha256=source_hashes, compiler=str(cc), flags=flags,
                  compiler_sha256=hashlib.sha256(cc.read_bytes()).hexdigest(),
                  compiler_version=subprocess.check_output([str(cc), '--version'], text=True).strip(),
                  commands=[command, link_command], results=rows, aliases=alias_checks,
                  external_symbols=SYMBOLS, alignment_gaps=ALIGNMENT_GAPS,
                  exact_objects=sum(r['exact'] for r in rows if r['origin'] == 'typed_initializer'),
                  total_objects=len(CASES),
                  typed_initializer_bytes=sum(r['expected_size'] for r in rows
                                              if r['origin'] == 'typed_initializer'),
                  linker_alignment_bytes=sum(g['size'] for g in ALIGNMENT_GAPS),
                  exact_bytes=sum(r['expected_size'] for r in rows if r['exact']),
                  total_bytes=sum(r['expected_size'] for r in rows))
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{report["exact_objects"]}/{report["total_objects"]} objects exact; '
          f'{report["exact_bytes"]}/{report["total_bytes"]} initialized RAM source/layout bytes '
          f'({report["linker_alignment_bytes"]} linker alignment bytes).')
    return int(not all(row['exact'] for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
