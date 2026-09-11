#!/usr/bin/env python3
"""Compare nine isolated stock/candidate DMA and interrupt-control routines.

Finite deterministic ordered MMIO/register-latch model, not real hardware
timing or binary equivalence. No peripheral side effects or calls are mocked.
Consumes fresh isolated byte-gate reports/ELFs; does not rebuild source.
"""
import argparse
from collections import Counter
import hashlib
import io
import itertools
import json
from pathlib import Path
import random
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn import arm_const as arm
from gd_function_gate import load

STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'
STOP, SP, CONFIG = 0x10000000, 0x24001f00, 0x24000100
MASK = 0xffffffff
AIRCR = 0xe000ed0c
SEED = 0x4744444d4143544c


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def fresh(hashes):
    for name, digest in hashes.items():
        path = ROOT / name
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError('stale input; rebuild the isolated gate: ' + name)


def inputs(paths):
    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != STOCK_MD5:
        raise ValueError('unexpected stock image')
    audit, functions, watched = [], [], {str(STOCK): sha(stock)}
    for filename, report_path in zip(('check-gd-dma-vendor.py',
                                      'check-gd-interrupt-control.py'), paths):
        profile = load(filename)
        report_blob = report_path.read_bytes()
        report = json.loads(report_blob)
        fresh(report['source_sha256'])
        required = {ROOT / 'tools' / filename,
                    ROOT / 'mcu/mainBoardGD/recovered' /
                    ('dma_vendor.c' if 'dma-vendor' in filename else 'interrupt_control.c'),
                    ROOT / 'mcu/mainBoardGD/recovered/mclib_hardware.h'}
        if not required <= {Path(p).resolve() for p in report['source_sha256']}:
            raise ValueError('missing required source/profile provenance: ' + filename)
        if report['stock_md5'] != STOCK_MD5:
            raise ValueError('report stock identity differs')
        watched.update(report['source_sha256'])
        watched[str(report_path)] = sha(report_blob)
        profile_audit = {key: report[key] for key in
                         ('compiler', 'compiler_sha256', 'flags', 'source_sha256')}
        profile_audit.update(report=str(report_path), report_sha256=sha(report_blob))
        audit.append(profile_audit)
        for name, address, size in profile.CASES:
            rows = [row for row in report['results'] if row['name'] == name]
            if len(rows) != 1:
                raise ValueError('missing or duplicate gate row: ' + name)
            row = rows[0]
            elf_path = report_path.parent / (name + '.elf')
            elf_blob = elf_path.read_bytes()
            watched[str(elf_path)] = sha(elf_blob)
            elf = ELFFile(io.BytesIO(elf_blob))
            section = elf.get_section_by_name('.text')
            symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(name)
            if section is None or section['sh_addr'] != address or not symbols or len(symbols) != 1:
                raise ValueError('missing/misplaced function section: ' + name)
            symbol = symbols[0]
            candidate = section.data()
            offset = address - 0x08000000 if address >= 0x08000000 else address + 0x4418
            expected = stock[offset:offset + size]
            if (symbol['st_info']['type'] != 'STT_FUNC' or
                    symbol['st_value'] != address | 1 or
                    row['address'] != address or row['expected_size'] != size or
                    row['actual_symbol_address'] != address or not row['entry_exact'] or
                    len(candidate) != row['actual_size'] or len(expected) != size or
                    sha(candidate) != row['actual_sha256'] or sha(expected) != row['expected_sha256']):
                raise ValueError('entry/bounds/byte hashes disagree with gate: ' + name)
            functions.append(dict(name=name, address=address, stock=expected,
                                  candidate=candidate, elf=str(elf_path), elf_sha256=sha(elf_blob),
                                  byte_exact=expected == candidate))
    if audit[0]['compiler_sha256'] != audit[1]['compiler_sha256'] or audit[0]['flags'] != audit[1]['flags']:
        raise ValueError('profiles do not use the same global compiler configuration')
    return functions, audit, watched


def execute(address, code, args, initial, config, seed):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    code_page = address & ~0xfff
    code_size = (address + len(code) - code_page + 0xfff) & ~0xfff
    for base, size in ((code_page, code_size), (0x24000000, 0x2000), (STOP, 0x1000)):
        cpu.mem_map(base, size)
    cpu.mem_write(address, code)
    rng = random.Random(seed)
    for index in range(13):
        cpu.reg_write(getattr(arm, 'UC_ARM_REG_R%d' % index), rng.getrandbits(32))
    saved = {getattr(arm, 'UC_ARM_REG_R%d' % i): cpu.reg_read(getattr(arm, 'UC_ARM_REG_R%d' % i))
             for i in range(4, 12)}
    for index in range(8, 16):
        register, value = getattr(arm, 'UC_ARM_REG_D%d' % index), rng.getrandbits(64)
        cpu.reg_write(register, value)
        saved[register] = value
    cpu.mem_write(SP - 0x100, rng.randbytes(0x100))
    config_blob = struct.pack('<10I', *config) if config is not None else b''
    if config_blob:
        cpu.mem_write(CONFIG, config_blob)
    cpu.reg_write(arm.UC_ARM_REG_SP, SP)
    cpu.reg_write(arm.UC_ARM_REG_LR, STOP | 1)
    for index, value in enumerate(args):
        cpu.reg_write(getattr(arm, 'UC_ARM_REG_R%d' % index), value)
    registers, trace = dict(initial), []

    def read(uc, offset, size, base):
        key = (base + offset, size)
        if key not in registers:
            raise ValueError('unexpected MMIO read address/width: %r' % (key,))
        value = registers[key]
        trace.append(('read', *key, value))
        return value

    def write(uc, offset, size, value, base):
        key = (base + offset, size)
        if key not in registers:
            raise ValueError('unexpected MMIO write address/width: %r' % (key,))
        value &= (1 << (size * 8)) - 1
        registers[key] = value
        trace.append(('write', *key, value))

    def instruction(uc, pc, size, _):
        if not address <= pc < pc + size <= address + len(code):
            raise ValueError('execution left audited body at %#x' % pc)

    for page in sorted({target & ~0xfff for target, _ in registers}):
        cpu.mmio_map(page, 0x1000, read, page, write, page)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    try:
        cpu.emu_start(address | 1, STOP, count=2000)
    except UcError as error:
        raise ValueError('emulation failure at %#x; last MMIO %r' %
                         (cpu.reg_read(arm.UC_ARM_REG_PC), trace[-8:])) from error
    if cpu.reg_read(arm.UC_ARM_REG_PC) != STOP or cpu.reg_read(arm.UC_ARM_REG_SP) != SP:
        raise ValueError('did not return to sentinel with SP restored')
    if any(cpu.reg_read(reg) != value for reg, value in saved.items()):
        raise ValueError('callee-saved r4-r11 or d8-d15 changed')
    if config_blob and bytes(cpu.mem_read(CONFIG, 40)) != config_blob:
        raise ValueError('DMA configuration input was modified')
    # All nine source/stock interfaces are void. Scratch r0 and condition
    # flags are not specified return values and are deliberately not compared.
    return dict(trace=trace, registers=[(*key, value) for key, value in sorted(registers.items())],
                returned=True, stack_restored=True, callee_saved_preserved=True,
                config_unchanged=True)


def scenarios(name):
    rng = random.Random(SEED)
    samples = (0, MASK, 0xaaaaaaaa, 0x55555555, 0x80000000, 0x7fffffff)
    flags = (0, 1, 2, 4, 8, 16, 32, 0x3d, 0x80, 0x81, 0xff, 0x100, MASK)
    if name.startswith('gd_motor_dma_'):
        for dma, channel in itertools.product((0x40020000, 0x40020400), range(8)):
            base = dma + channel * 24
            targets = [base + offset for offset in (0x10, 0x14, 0x18, 0x1c, 0x20, 0x24)]
            targets += [dma + (8 if channel < 4 else 12)]
            if name.endswith('_init'):
                mux = (0x40020000 | channel << 2) + (0x800 if dma == 0x40020000 else 0x820)
                for increment, memory, circular in itertools.product((0, 1, 2, MASK), repeat=3):
                    for fill in (0, MASK, None):
                        config = [rng.getrandbits(32) for _ in range(10)]
                        config[2], config[4], config[6] = increment, memory, circular
                        registers = {(target, 4): rng.getrandbits(32) if fill is None else fill
                                     for target in (*targets, mux)}
                        yield (dma, channel, CONFIG), registers, config
            else:
                arguments = flags if name.endswith(('_flag_clear', '_interrupt_enable')) else (None,)
                for flag, fill in itertools.product(arguments, (*samples, None)):
                    registers = {(target, 4): rng.getrandbits(32) if fill is None else fill
                                 for target in targets}
                    yield (dma, channel) if flag is None else (dma, channel, flag), registers, None
    elif name == 'nvic_irq_enable':
        irqs = (0, 1, 15, 31, 32, 63, 64, 127, 128, 239, 255, 256, 511, MASK)
        for irq, group in itertools.product(irqs, range(8)):
            for preemption, subpriority in ((0, 0), (1, 1), (15, 15), (16, 32),
                                            (MASK, MASK), (rng.getrandbits(32), rng.getrandbits(32))):
                priority = ((irq | 0xe000e100) + 0x300) & MASK
                enable = 0xe000e100 + ((irq >> 3) & 0x1c)
                registers = {(AIRCR, 4): (rng.getrandbits(32) & ~0x700) | group << 8,
                             (priority, 1): rng.getrandbits(8), (enable, 4): rng.getrandbits(32)}
                yield (irq, preemption, subpriority), registers, None
    elif name == 'nvic_priority_group_set':
        for group, previous in itertools.product((*range(0, 0x800, 0x100), 1, 0x7000, MASK),
                                                  (*samples, rng.getrandbits(32))):
            yield (group,), {(AIRCR, 4): previous}, None
    else:
        for source, locked in itertools.product((*range(256), 0x100, 0x12345678, MASK), (False, True)):
            target = 0x40018400 | (source & 0xfc)
            for destination in (0, 1, 0xff, 0x100, MASK, rng.getrandbits(32)):
                previous = (rng.getrandbits(32) & 0x7fffffff) | int(locked) << 31
                yield (source, destination), {(target, 4): previous}, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dma-report', type=Path, default=ROOT / 'work/mainBoardGD-dma-vendor/results.json')
    parser.add_argument('--interrupt-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-interrupt-control/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-dma-control-mmio.json')
    args = parser.parse_args()
    functions, profiles, watched = inputs([args.dma_report.resolve(), args.interrupt_report.resolve()])
    watched[str(Path(__file__).resolve())] = sha(Path(__file__).read_bytes())
    report = dict(scope='finite ordered MMIO register-latch comparison, not hardware or byte equivalence',
                  stock_md5=STOCK_MD5, stock_sha256=watched[str(STOCK)],
                  profiles=profiles, input_sha256=watched, seed=SEED,
                  checker_sha256=watched[str(Path(__file__).resolve())],
                  unicorn_version=unicorn.__version__, mocked_calls=[],
                  whole_image_verified=False, actual_hardware_verified=False,
                  limitations=['Finite deterministic cases; DMA channels 0..7 and both DMA bases.',
                               'Ordinary register latches, not W1C/W0C, NVIC/AIRCR reset side effects, interrupts or bus timing.',
                               'Config words and MMIO contents include arbitrary 32-bit values; no concurrent mutation.',
                               'All interfaces are void: return-to-caller, SP, r4-r11 and d8-d15 checked; caller-scratch registers ignored.'],
                  results=[])
    success = True
    for function in functions:
        total = passed = 0
        failures, events, digest = [], Counter(), hashlib.sha256()
        for arguments, registers, config in scenarios(function['name']):
            total += 1
            try:
                expected = execute(function['address'], function['stock'], arguments, registers, config, SEED + total)
                actual = execute(function['address'], function['candidate'], arguments, registers, config, SEED + total)
                exact = expected == actual
                events.update(event[0] for event in actual['trace'])
                digest.update(json.dumps([arguments, sorted(registers.items()), config, expected, actual],
                                         sort_keys=True).encode())
                if not exact and len(failures) < 4:
                    failures.append(dict(case_index=total, register_seed=SEED + total,
                                         arguments=arguments, initial_registers=sorted(registers.items()),
                                         config=config, stock=expected, candidate=actual))
            except ValueError as error:
                exact = False
                if len(failures) < 4:
                    failures.append(dict(case_index=total, register_seed=SEED + total,
                                         arguments=arguments, initial_registers=sorted(registers.items()),
                                         config=config, error=str(error)))
            passed += exact
        success &= total == passed
        row = {key: value for key, value in function.items() if key not in ('stock', 'candidate')}
        row.update(stock_size=len(function['stock']), candidate_size=len(function['candidate']),
                   stock_sha256=sha(function['stock']), candidate_sha256=sha(function['candidate']),
                   cases=total, passing_cases=passed, trace_and_abi_exact=passed == total,
                   event_counts=events, execution_digest=digest.hexdigest(), first_failures=failures)
        report['results'].append(row)
        print('%s: %d/%d ordered MMIO/ABI cases %s' %
              (function['name'], passed, total, 'PASS' if passed == total else 'DIFF'), flush=True)
    fresh(watched)
    report['all_trace_cases_exact'] = success
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print('Register-latch model only; report: ' + str(args.out))
    return int(not success)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit('DMA/control MMIO check failed: ' + str(error))
