#!/usr/bin/env python3
"""Bounded stepper-loader state/call-ABI model; not hardware validation.

Executes the complete stock/candidate loader and actual stock queue-empty/pop
helpers. GPIO toggle and move_free are mocked calls, recording arguments and
the complete stepper state visible at each call. No firmware is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import sys

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
ENTRY, SIZE, STOCK_OFFSET = 0x4850, 96, 0x4418
CONFIG, MOVE, STOP, STACK = 0x24000000, 0x24001000, 0x10000000, 0x2400f000
SEED = 0x485048b0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def inputs(report_path, elf_path):
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    for filename, expected in report['source_sha256'].items():
        if digest((ROOT / filename).read_bytes()) != expected:
            raise ValueError('stale isolated source: ' + filename)
    stock_path = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
    stock = stock_path.read_bytes()
    if hashlib.md5(stock).hexdigest() != report['stock_md5']:
        raise ValueError('stock image differs from isolated report')
    if hashlib.md5(stock).hexdigest() != 'fb64911bac422a27d7ed7fab3597603f':
        raise ValueError('unexpected mainBoardGD stock image')
    rows = [row for row in report['results'] if row['name'] == 'stepper_load_next']
    if len(rows) != 1:
        raise ValueError('missing/ambiguous loader gate row')
    row = rows[0]
    if row['address'] != ENTRY or row['expected_size'] != SIZE:
        raise ValueError('incorrect full loader extent')
    expected = stock[STOCK_OFFSET + ENTRY:STOCK_OFFSET + ENTRY + SIZE]
    if digest(expected) != row['expected_sha256']:
        raise ValueError('stale expected loader bytes')
    elf_bytes = elf_path.read_bytes()
    with elf_path.open('rb') as stream:
        elf = ELFFile(stream)
        section = elf.get_section_by_name('.text')
        symbols = elf.get_section_by_name('.symtab').get_symbol_by_name('stepper_load_next')
        if (section is None or section['sh_addr'] != ENTRY or not symbols
                or len(symbols) != 1 or symbols[0]['st_value'] & ~1 != ENTRY
                or symbols[0]['st_info']['type'] != 'STT_FUNC'):
            raise ValueError('invalid loader ELF entry/section')
        candidate = section.data()
        if len(candidate) != row['actual_size'] or digest(candidate) != row['actual_sha256']:
            raise ValueError('stale candidate loader bytes')
        if len(candidate) > SIZE or symbols[0]['st_size'] != len(candidate):
            raise ValueError('candidate is not a complete fitting loader function')
    provenance = dict(stock_sha256=digest(stock), isolated_report_sha256=digest(report_bytes),
                      source_sha256=report['source_sha256'], candidate_elf_sha256=digest(elf_bytes),
                      expected_loader_sha256=digest(expected), candidate_loader_sha256=digest(candidate),
                      stock_queue_helpers_sha256={hex(address): digest(
                          stock[STOCK_OFFSET + address:STOCK_OFFSET + address + 10])
                          for address in (0x3e30, 0x3e48)},
                      checker_sha256=digest(Path(__file__).read_bytes()),
                      report_path=str(report_path), elf_path=str(elf_path))
    return stock[STOCK_OFFSET:], expected, candidate, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path,
                        default=ROOT / 'work/mainBoardGD-stepper/results.json')
    parser.add_argument('--elf', type=Path,
                        default=ROOT / 'work/mainBoardGD-stepper/stepper_load_next.elf')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'work/mainBoardGD-stepper-load-model.json')
    args = parser.parse_args()
    stock, expected_body, candidate_body, provenance = inputs(args.report, args.elf)
    sys.path.insert(0, str(ROOT / 'work/python-deps'))
    import unicorn
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                  UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                                  UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
                                  UC_ARM_REG_R10, UC_ARM_REG_R11,
                                  UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
    argument_regs = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)
    preserved_regs = (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                      UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)

    def run(body, parameter, node):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for address, length in ((0, 0x10000), (CONFIG, 0x10000), (STOP, 0x1000)):
            cpu.mem_map(address, length)
        cpu.mem_write(0, stock)
        cpu.mem_write(ENTRY, body)
        cpu.mem_write(CONFIG, parameter)
        cpu.mem_write(MOVE, node)
        cpu.mem_write(STACK - 128, bytes([0xa5]) * 144)
        trace = []

        def instruction(machine, pc, size, _):
            if pc in (0x3320, 0x3e18):
                count = 3 if pc == 0x3320 else 1
                trace.append(dict(address=pc,
                                  arguments=[machine.reg_read(r) for r in argument_regs[:count]],
                                  stepper=bytes(machine.mem_read(CONFIG, 80)).hex()))
                machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
            elif not (ENTRY <= pc < ENTRY + len(body)
                      or 0x3e30 <= pc < 0x3e3a or 0x3e48 <= pc < 0x3e52
                      or pc == STOP):
                raise AssertionError(f'unexpected instruction address {pc:#x}')

        cpu.hook_add(UC_HOOK_CODE, instruction)
        cpu.reg_write(UC_ARM_REG_R0, CONFIG)
        for index, register in enumerate(preserved_regs):
            cpu.reg_write(register, 0x12340000 + index)
        cpu.reg_write(UC_ARM_REG_SP, STACK)
        cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
        cpu.emu_start(ENTRY | 1, STOP, count=1000)
        assert cpu.reg_read(UC_ARM_REG_PC) == STOP
        assert cpu.reg_read(UC_ARM_REG_SP) == STACK
        assert all(cpu.reg_read(register) == 0x12340000 + i
                   for i, register in enumerate(preserved_regs))
        assert bytes(cpu.mem_read(STACK, 16)) == bytes([0xa5]) * 16
        assert bytes(cpu.mem_read(STACK - 128, 64)) == bytes([0xa5]) * 64
        return dict(stepper=bytes(cpu.mem_read(CONFIG, 80)).hex(),
                    move=bytes(cpu.mem_read(MOVE, 16)).hex(),
                    return_value=cpu.reg_read(UC_ARM_REG_R0), calls=trace)

    rng = random.Random(SEED)
    rows = []
    for empty in (0, 1):
        for flags in (0, 1, 2, 3, 254, 255):
            for add in (-32768, -1, 0, 1, 32767):
                for steps in (0, 1, 2, 32767, 65535):
                    for interval in (0, 1, 0x7fffffff, 0xffffffff):
                        parameter = bytearray(rng.randbytes(80))
                        struct.pack_into('<II', parameter, 60, 0 if empty else MOVE, MOVE)
                        node = struct.pack('<IIhHB3x', MOVE + 32, interval, add, steps, flags)
                        expected = run(expected_body, bytes(parameter), node)
                        actual = run(candidate_body, bytes(parameter), node)
                        case = dict(empty=bool(empty), flags=flags, add=add,
                                    count=steps, interval=interval,
                                    stepper_input=parameter.hex(), move_input=node.hex())
                        if actual != expected:
                            raise AssertionError(dict(case=case, expected=expected, actual=actual))
                        rows.append(dict(inputs=case, expected_output_sha256=fingerprint(expected),
                                         candidate_output_sha256=fingerprint(actual),
                                         return_value=actual['return_value'],
                                         mocked_calls=actual['calls'], passed=True))
    result = dict(scope='modeled state/queue/return/call ABI, not hardware or timing validation',
                  actual_dependencies=['stock move_queue_empty@0x3e30', 'stock move_queue_pop@0x3e48'],
                  mocked_dependencies=['gpio_out_toggle_noirq@0x3320', 'move_free@0x3e18'],
                  limitations=['no actual GPIO effects or free-list mutation',
                               'queue objects and stepper/move allocations are disjoint',
                               'bounded deterministic cases, not exhaustive equivalence'],
                  seed=SEED, unicorn_version=unicorn.__version__, provenance=provenance,
                  passed=len(rows), results=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(rows)} loader state/queue/return/call-ABI cases passed: {args.out}')


if __name__ == '__main__':
    main()
