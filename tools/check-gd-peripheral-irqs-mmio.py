#!/usr/bin/env python3
"""Verify ADC/DMA interrupt helper ARM behavior against stock and an oracle.

Consumes the audited partial ELF without rebuilding. Checks full ordered MMIO,
return values and final modeled registers. The finite register-latch model is
not hardware validation: interrupts, bus timing and W0C/W1C peripheral side
effects are not simulated. No calls are mocked; each helper executes in full.
Requires pyelftools and Unicorn (work/python-deps is supported).
"""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import (Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS,
                     UC_HOOK_CODE)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR,
                               UC_CPU_ARM_CORTEX_M7)

STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
MD5 = 'fb64911bac422a27d7ed7fab3597603f'
STOP, STACK = 0x10000000, 0x24000f00
PROFILES = [('adc_interrupt_flag_clear', 0x4d8, 6),
            ('adc_interrupt_flag_get', 0x4e0, 150),
            ('dma_interrupt_flag_clear', 0x2b28, 56),
            ('dma_interrupt_flag_get', 0x2b60, 300)]
DMA_FLAGS = {1: (0x24, 0x80), 4: (0x10, 2), 8: (0x10, 4),
             16: (0x10, 8), 32: (0x10, 16)}
ADC_FLAGS = {1: 1 << 6, 2: 1 << 5, 4: 1 << 7, 32: 1 << 26,
             0x40000000: 1 << 30, 0x80000000: 1 << 31}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fresh_sources(hashes):
    required = {ROOT / 'mcu/mainBoardGD/recovered/adc_interrupts.c',
                ROOT / 'mcu/mainBoardGD/recovered/dma_interrupts.c'}
    if not required <= {(ROOT / name).resolve() for name in hashes}:
        raise ValueError('partial report lacks ADC/DMA source provenance')
    for name, digest in hashes.items():
        path = ROOT / name
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError('stale partial report; rebuild before checking: ' + name)


def load_inputs(report_path, elf_path):
    report_blob = report_path.read_bytes()
    partial = json.loads(report_blob)
    fresh_sources(partial['source_sha256'])
    if elf_path is None:
        elf_path = ROOT / partial['linked_elf']
    elf_path = elf_path.resolve()
    if elf_path != (ROOT / partial['linked_elf']).resolve():
        raise ValueError('--elf must match partial report linked_elf')
    elf_blob, stock = elf_path.read_bytes(), STOCK.read_bytes()
    if sha(elf_blob) != partial['linked_elf_sha256']:
        raise ValueError('ELF hash disagrees with partial report')
    if hashlib.md5(stock).hexdigest() != MD5 or partial['stock_md5'] != MD5:
        raise ValueError('unexpected stock image for fixed address profile')
    elf = ELFFile(io.BytesIO(elf_blob))
    code, functions = {}, []
    for name, address, size in PROFILES:
        rows = [row for row in partial['results'] if row['name'] == name]
        if len(rows) != 1:
            raise ValueError('missing/ambiguous partial row: ' + name)
        row = rows[0]
        section = elf.get_section_by_name(row['output_section'])
        if section is None or section['sh_addr'] != address:
            raise ValueError('missing/misplaced actual function: ' + name)
        actual = section.data()
        expected = stock[0x4418 + address:0x4418 + address + size]
        if (row['address'] != address or row['size'] != size or
                len(actual) != row['actual_size'] or len(actual) > size or
                len(expected) != size or sha(expected) != row['expected_sha256'] or
                sha(actual) != row['actual_sha256']):
            raise ValueError('stock/ELF bounds or hashes disagree with partial row: ' + name)
        code[name] = expected, actual
        functions.append(dict(name=name, address=address, stock_size=size,
                              candidate_size=len(actual), byte_exact=actual == expected,
                              expected_sha256=sha(expected), actual_sha256=sha(actual)))
    provenance = dict(stock_md5=MD5, stock_sha256=sha(stock),
        partial_report=str(report_path), partial_report_sha256=sha(report_blob),
        linked_elf=str(elf_path), linked_elf_sha256=sha(elf_blob),
        source_sha256=partial['source_sha256'], functions=functions,
        compiler=partial['compiler'], compiler_sha256=partial['compiler_sha256'],
        flags=partial['flags'], checker_sha256=sha(Path(__file__).read_bytes()),
        unicorn_version=unicorn.__version__)
    return code, provenance


def execute(name, address, code, args, initial):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    for base, size in ((0, 0x10000), (0x24000000, 0x1000), (STOP, 0x1000)):
        cpu.mem_map(base, size)
    cpu.mem_write(address, code)
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2), args):
        cpu.reg_write(reg, value)
    registers, trace = dict(initial), []

    def read(uc, offset, size, base):
        target = base + offset
        if size != 4 or target not in registers:
            raise ValueError('unexpected peripheral read: %r' % ((target, size),))
        value = registers[target]
        trace.append(('read', target, size, value))
        return value

    def write(uc, offset, size, value, base):
        target = base + offset
        if size != 4 or target not in registers:
            raise ValueError('unexpected peripheral write: %r' % ((target, size),))
        registers[target] = value
        trace.append(('write', target, size, value))

    def instruction(uc, pc, size, _):
        if not (address <= pc and pc + size <= address + len(code)):
            raise ValueError('execution outside audited function at %#x' % pc)

    # Map only pages required by this case; unexpected register accesses fail
    # explicitly rather than getting a fabricated zero from a broad MMIO map.
    for base in sorted({target & ~0xfff for target in registers}):
        cpu.mmio_map(base, 0x1000, read, base, write, base)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    try:
        cpu.emu_start(address | 1, STOP, count=1000)
    except UcError as error:
        raise ValueError('emulation failed at PC=%#x after %r' %
                         (cpu.reg_read(UC_ARM_REG_PC), trace[-8:])) from error
    if cpu.reg_read(UC_ARM_REG_PC) != STOP or cpu.reg_read(UC_ARM_REG_SP) != STACK:
        raise ValueError('function failed to return with its stack restored')
    return dict(trace=trace, registers=registers,
                result=cpu.reg_read(UC_ARM_REG_R0) if name.endswith('_get') else None)


def oracle(name, args, initial):
    """Independent mask/address specification; no candidate/stock execution."""
    final, trace = dict(initial), []
    if name == 'dma_interrupt_flag_clear':
        dma, channel, flag = args
        target = dma + (8 if channel < 4 else 12)
        shift = (0, 6, 16, 22)[channel % 4]
        value = initial[target] | ((flag << shift) & 0xffffffff)
        trace = [('read', target, 4, initial[target]), ('write', target, 4, value)]
        final[target] = value
        result = None
    elif name == 'adc_interrupt_flag_clear':
        adc, flag = args
        value = flag ^ 0xffffffff
        trace = [('write', adc, 4, value)]
        final[adc] = value
        result = None
    elif name == 'dma_interrupt_flag_get':
        dma, channel, flag = args
        result = 0
        if flag in DMA_FLAGS:
            offset, enable = DMA_FLAGS[flag]
            status_address = dma + (0 if channel < 4 else 4)
            control_address = dma + 24 * channel + offset
            status, control = initial[status_address], initial[control_address]
            mask = flag << (0, 6, 16, 22)[channel % 4]
            trace = [('read', status_address, 4, status), ('read', control_address, 4, control)]
            result = int(bool(status & mask) and bool(control & enable))
    else:
        adc, flag = args
        result = 0
        if flag in ADC_FLAGS:
            status, control = initial[adc], initial[adc + 4]
            trace = [('read', adc, 4, status), ('read', adc + 4, 4, control)]
            result = int(bool(status & flag) and bool(control & ADC_FLAGS[flag]))
    return dict(trace=trace, registers=final, result=result)


def scenarios(name):
    rng = random.Random(0x4757444d41)
    dma_bases = (0x40020000, 0x40020400)
    adc_bases = (0x40012400, 0x40012800)  # observed motor IRQ callers
    if name == 'dma_interrupt_flag_get':
        for dma in dma_bases:
            for channel in range(8):
                for flag in (*range(256), 0x10000, 0xffffffff):
                    for bits in range(4):
                        offset, enable = DMA_FLAGS.get(flag, (0x10, 0))
                        pending = (flag << (0, 6, 16, 22)[channel % 4]) if enable else 0
                        status = rng.getrandbits(32) & ~pending
                        control = rng.getrandbits(32) & ~enable
                        if bits & 1:
                            status |= pending
                        if bits & 2:
                            control |= enable
                        yield (dma, channel, flag), {dma + (4 if channel >= 4 else 0): status,
                                                     dma + 24 * channel + offset: control}
    elif name == 'adc_interrupt_flag_get':
        for adc in adc_bases:
            for flag in (*range(256), 0x40000000, 0x80000000, 0xc0000000, 0xffffffff):
                for bits in range(4):
                    enable = ADC_FLAGS.get(flag, 0)
                    pending = flag if enable else 0
                    status = rng.getrandbits(32) & ~pending
                    control = rng.getrandbits(32) & ~enable
                    if bits & 1:
                        status |= pending
                    if bits & 2:
                        control |= enable
                    yield (adc, flag), {adc: status, adc + 4: control}
    elif name == 'dma_interrupt_flag_clear':
        for dma in dma_bases:
            for channel in range(8):
                for flag in (0, 1, 4, 8, 16, 32, 0x3d, 0x100, 0xffffffff):
                    for previous in (0, rng.getrandbits(32), 0xffffffff):
                        yield (dma, channel, flag), {dma + (12 if channel >= 4 else 8): previous}
    else:
        for adc in adc_bases:
            for flag in (0, 1, 2, 3, 4, 8, 32, 0x40000000, 0x80000000, 0xc0000000, 0xffffffff):
                for previous in (0, rng.getrandbits(32), 0xffffffff):
                    yield (adc, flag), {adc: previous}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-partial/results.json')
    parser.add_argument('--elf', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-peripheral-irqs-mmio.json')
    args = parser.parse_args()
    code, report = load_inputs(args.partial_report, args.elf)
    report.update(scope='ADC/DMA interrupt helper modeled MMIO, not hardware or binary equivalence',
        whole_image_verified=False, actual_hardware_verified=False, mocked_calls=[],
        limitations=['DMA channels restricted to SDK-supported range 0..7.',
                     'Finite deterministic flags/register samples; unrelated bits randomized.',
                     'Writes update register latches only; W0C/W1C effects, interrupts and bus timing are not modeled.'],
        results=[])
    all_exact = True
    for name, address, _ in PROFILES:
        total, passed, events = 0, 0, Counter()
        failures, digest = [], hashlib.sha256()
        for arguments, registers in scenarios(name):
            total += 1
            expected_model = oracle(name, arguments, registers)
            try:
                expected = execute(name, address, code[name][0], arguments, registers)
                actual = execute(name, address, code[name][1], arguments, registers)
                exact = expected == actual == expected_model
                events.update(t[0] for t in actual['trace'])
                digest.update(json.dumps([arguments, registers, expected, actual, expected_model],
                                         sort_keys=True).encode())
                if not exact and len(failures) < 4:
                    failures.append(dict(arguments=arguments, initial_registers=registers,
                                         stock=expected, candidate=actual, oracle=expected_model))
            except ValueError as error:
                exact = False
                if len(failures) < 4:
                    failures.append(dict(arguments=arguments, initial_registers=registers,
                                         error=str(error)))
            passed += exact
        all_exact &= passed == total
        report['results'].append(dict(name=name, cases=total, passing_cases=passed,
            trace_and_oracle_exact=passed == total, event_counts=events,
            execution_digest=digest.hexdigest(), first_failures=failures))
        print('%s: %d/%d MMIO/result/oracle cases %s' %
              (name, passed, total, 'EXACT' if passed == total else 'DIFF'), flush=True)
    fresh_sources(report['source_sha256'])
    if (sha(args.partial_report.read_bytes()) != report['partial_report_sha256'] or
            sha(Path(report['linked_elf']).read_bytes()) != report['linked_elf_sha256']):
        raise ValueError('partial build changed during verification; rerun')
    report['all_trace_cases_exact'] = all_exact
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print('Modeled behavior only; inspect byte_exact separately. Report: ' + str(args.out))
    return int(not all_exact)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        sys.exit('Peripheral IRQ MMIO check failed: ' + str(error))
