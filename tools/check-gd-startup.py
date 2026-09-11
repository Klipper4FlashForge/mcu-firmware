#!/usr/bin/env python3
"""Compare recovered startup bytes and emulate its MMIO trace against stock.

Requires pyelftools and Unicorn (project-local work/python-deps is supported).
The peripheral model supplies deterministic readiness transitions. This proves
the observed read/write sequence for these scenarios, not real board operation
or a complete firmware match. Byte differences are reported separately.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
from unicorn.arm_const import UC_CPU_ARM_CORTEX_M7

FLASH = 0x08000000
ENTRY = FLASH + 0x620
STOP = 0x10000000
CONTROL = 0x58024400
CONFIG = CONTROL + 8


def toolchain():
    spec = importlib.util.spec_from_file_location('gd_toolchain',
                          ROOT / 'tools/check-gd-toolchain.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(code, seed, delays, fail_oscillator=False):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    for base, size in ((FLASH, 0x10000), (0x24000000, 0x10000), (STOP, 0x1000)):
        cpu.mem_map(base, size)
    for address, blob in code:
        cpu.mem_write(address, blob)
    rng, registers = random.Random(seed), {}
    for offset in range(0, 0x100, 4):
        value = rng.getrandbits(32)
        if offset == 0:
            value &= ~0xc3030000
        if offset == 8:
            value &= ~15
        registers[CONTROL + offset] = value
    registers[0x58000468] = rng.getrandbits(32)
    cpu.reg_write(UC_ARM_REG_SP, 0x2400f000)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    trace, polls, previous = [], [0, 0, 0, 0], [None]
    trapped = [False]

    def read_register(uc, offset, size, base):
        address = base + offset
        assert size == 4
        value = registers.get(address, 0)
        if address == CONTROL:
            for index, enabled, ready in ((0, 1 << 30, 1 << 31),
                                               (1, 1 << 16, 1 << 17),
                                               (2, 1 << 24, 1 << 25)):
                value &= ~ready
                if value & enabled:
                    polls[index] += 1
                    if polls[index] >= delays[index] and not (
                            fail_oscillator and index == 1):
                        value |= ready
                else:
                    polls[index] = 0
        elif address == CONFIG:
            value &= ~12
            if value & 3 == 3:
                polls[3] += 1
                if polls[3] >= delays[3]:
                    value |= 12
            else:
                polls[3] = 0
        registers[address] = value
        trace.append(('read', address, size, value))
        return value

    def write_register(uc, offset, size, value, base):
        assert size == 4
        address = base + offset
        registers[address] = value
        trace.append(('write', address, size, value))

    def instruction(uc, address, size, _):
        if address == previous[0]:
            trapped[0] = True
            uc.emu_stop()
        previous[0] = address

    for base, size in ((0x58000000, 0x1000), (0x58024000, 0x2000),
                       (0xe000e000, 0x2000)):
        cpu.mmio_map(base, size, read_register, base, write_register, base)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    try:
        cpu.emu_start(ENTRY | 1, STOP, count=1000000)
    except UcError as error:
        raise ValueError('emulation failed at PC=%#x r0=%#x r1=%#x r2=%#x after %r' %
                         (cpu.reg_read(UC_ARM_REG_PC), cpu.reg_read(UC_ARM_REG_R0),
                          cpu.reg_read(UC_ARM_REG_R1), cpu.reg_read(UC_ARM_REG_R2),
                          trace[-6:])) from error
    outcome = 'returned' if cpu.reg_read(UC_ARM_REG_PC) == STOP else (
        'trapped' if trapped[0] else 'instruction_limit')
    return outcome, trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('MCU_GD_CC'))
    parser.add_argument('--cflag', action='append', default=[],
                        help='explicit diagnostic flag, e.g. --cflag=-fno-unroll-loops')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-startup.json')
    args = parser.parse_args()
    tc = toolchain()
    cc = tc.compiler_path(args.cc)
    stock = tc.STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != tc.STOCK_MD5:
        raise ValueError('unexpected stock image for startup address profile')
    flags = tc.FLAGS + args.cflag + ['-I' + str(ROOT / 'klipper/lib/cmsis-core')]
    report = {'scope': 'isolated startup code and modeled MMIO, not whole firmware',
              'stock_md5': tc.STOCK_MD5, 'compiler': str(cc), 'flags': flags,
              'source_sha256': {
                  str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in [ROOT / 'mcu/mainBoardGD/recovered/system_init.c',
                               ROOT / 'mcu/mainBoardGD/recovered/nvic.c']},
              'functions': [], 'trace_cases': []}
    with tempfile.TemporaryDirectory(prefix='gd-startup-', dir=ROOT / 'work') as temp:
        build = Path(temp)
        objects = []
        for unit in ('system_init', 'nvic'):
            obj = build / (unit + '.o')
            subprocess.run([str(cc), *flags, '-c',
                            str(ROOT / ('mcu/mainBoardGD/recovered/' + unit + '.c')),
                            '-o', str(obj)], check=True)
            objects.append(str(obj))
        link = build / 'check.ld'
        link.write_text('SECTIONS {\n'
            ' .init 0x08000620 : { *(.text.SystemInit) }\n'
            ' .nvic 0x08002090 : { *(.text.nvic_vector_table_set) }\n'
            ' /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }\n}\n')
        elf = build / 'check.elf'
        subprocess.run([str(cc), *tc.FLAGS[:4], '-nostdlib', '-Wl,-T,' + str(link),
                        '-Wl,--entry=SystemInit', *objects, '-o', str(elf)], check=True)
        with elf.open('rb') as stream:
            parsed = ELFFile(stream)
            code = [(s['sh_addr'], s.data()) for s in parsed.iter_sections()
                    if s['sh_flags'] & 2 and s['sh_type'] == 'SHT_PROGBITS']
            for section, name, address, size in (
                    ('.init', 'SystemInit', ENTRY, 548),
                    ('.nvic', 'nvic_vector_table_set', FLASH + 0x2090, 28)):
                candidate = parsed.get_section_by_name(section).data()
                expected = stock[address - FLASH:address - FLASH + size]
                entry = dict(name=name, address=address, stock_size=size,
                             candidate_size=len(candidate), byte_exact=candidate == expected,
                             expected_sha256=hashlib.sha256(expected).hexdigest(),
                             actual_sha256=hashlib.sha256(candidate).hexdigest(),
                             same_position_bytes=sum(a == b for a, b in zip(candidate, expected)))
                report['functions'].append(entry)
                print('%s: %d/%d bytes, size %d; %s' %
                      (name, entry['same_position_bytes'], size, len(candidate),
                       'EXACT' if entry['byte_exact'] else 'DIFF'))
        cases = [('immediate', 0, (1, 1, 1, 1), False),
                 ('delayed', 17, (5, 7, 11, 13), False),
                 ('different_reset_bits', 81, (2, 3, 4, 5), False),
                 ('oscillator_timeout', 99, (1, 1, 1, 1), True)]
        for name, seed, delays, fail in cases:
            expected = execute([(FLASH, stock)], seed, delays, fail)
            actual = execute(code, seed, delays, fail)
            if expected != actual:
                mismatch = next((i for i, pair in enumerate(zip(expected[1], actual[1]))
                                 if pair[0] != pair[1]), min(len(expected[1]), len(actual[1])))
                raise ValueError('%s differs at trace[%d]: stock %r vs recovered %r; '
                                 'outcomes %s/%s' % (name, mismatch,
                                 expected[1][mismatch:mismatch+1], actual[1][mismatch:mismatch+1],
                                 expected[0], actual[0]))
            if expected[0] != ('trapped' if fail else 'returned'):
                raise ValueError('unexpected stock execution outcome: ' + expected[0])
            report['trace_cases'].append(dict(name=name, outcome=actual[0],
                                              accesses=len(actual[1]), trace_exact=True))
            print('%s: %d MMIO accesses EXACT; %s' % (name, len(actual[1]), actual[0]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print('MMIO traces pass; inspect byte_exact fields for code-match status.')


if __name__ == '__main__':
    main()
