#!/usr/bin/env python3
"""Compare stock/recovered board_main MMIO and barriers without rebuilding.

Actual linked MPU helpers and bridges execute. Only gd_jscope_init and
sched_main are mocked. This is a finite deterministic MMIO model, not a board
boot test, MPU permission/cache simulation, or proof of binary equivalence.
Requires pyelftools, Capstone and Unicorn; work/python-deps is supported.
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
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
                               UC_ARM_REG_R0, UC_CPU_ARM_CORTEX_M7)

STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'
FLASH, ITCM_OFFSET, ENTRY, STOP = 0x08000000, 0x4418, 0x38b0, 0x10000000
SP = 0x2400f000
CCR, SHCSR, CCSIDR, CSSELR = 0xe000ed14, 0xe000ed24, 0xe000ed80, 0xe000ed84
CTRL, RNR, RBAR, RASR = 0xe000ed94, 0xe000ed98, 0xe000ed9c, 0xe000eda0
ICIALLU, DCISW = 0xe000ef50, 0xe000ef60
MOCKS = {0x5be4: 'gd_jscope_init', 0x4238: 'sched_main'}
PROFILES = (
    ('gd_board_main', ENTRY, 298),
    ('mpu_region_config', 0x08001f88, 78),
    ('mpu_region_enable', 0x08001fd8, 18),
    ('mpu_region_struct_para_init', 0x08001ff0, 26),
    ('gd_bridge_00005bc6', 0x5bc6, 10),
    ('gd_bridge_00005bd0', 0x5bd0, 10),
    ('gd_bridge_00005bda', 0x5bda, 10),
)
REQUIRED_SOURCES = (
    'mcu/mainBoardGD/recovered/board_main.c',
    'mcu/mainBoardGD/recovered/mpu.c',
    'mcu/mainBoardGD/recovered/mpu.h',
    'klipper/lib/cmsis-core/core_cm7.h',
    'klipper/lib/cmsis-core/cachel1_armv7.h',
    'klipper/lib/cmsis-core/mpu_armv7.h',
)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def source_freshness(hashes):
    missing = sorted(set(REQUIRED_SOURCES) - set(hashes))
    if missing:
        raise ValueError('partial report lacks required source hashes: ' + ', '.join(missing))
    stale = [name for name, digest in hashes.items()
             if not (ROOT / name).is_file() or sha((ROOT / name).read_bytes()) != digest]
    if stale:
        raise ValueError('stale partial report; rebuild before checking: ' + ', '.join(stale))


def load_inputs(report_path, elf_path):
    report_blob = report_path.read_bytes()
    report = json.loads(report_blob)
    source_freshness(report['source_sha256'])
    if elf_path is None:
        elf_path = ROOT / report['linked_elf']
    elf_path = elf_path.resolve()
    if elf_path != (ROOT / report['linked_elf']).resolve():
        raise ValueError('--elf must be the linked_elf identified by the partial report')
    elf_blob, stock = elf_path.read_bytes(), STOCK.read_bytes()
    if sha(elf_blob) != report['linked_elf_sha256']:
        raise ValueError('linked ELF hash differs from the partial report; rebuild before checking')
    if hashlib.md5(stock).hexdigest() != STOCK_MD5 or report['stock_md5'] != STOCK_MD5:
        raise ValueError('wrong stock image/address profile')
    elf = ELFFile(io.BytesIO(elf_blob))
    expected_code, actual_code, functions = [], [], []
    for name, address, size in PROFILES:
        rows = [r for r in report['results'] if r['name'] == name]
        if len(rows) != 1:
            raise ValueError('missing/ambiguous partial result: ' + name)
        row = rows[0]
        section = elf.get_section_by_name(row['output_section'])
        if section is None or section['sh_addr'] != address:
            raise ValueError('missing/misplaced linked section: ' + name)
        actual = section.data()
        offset = address - FLASH if address >= FLASH else address + ITCM_OFFSET
        expected = stock[offset:offset + size]
        if (row['address'] != address or row['size'] != size or
                len(expected) != size or len(actual) != row['actual_size'] or
                len(actual) > size or sha(actual) != row['actual_sha256'] or
                sha(expected) != row['expected_sha256']):
            raise ValueError('section bytes/bounds do not match partial report: ' + name)
        expected_code.append((address, expected))
        actual_code.append((address, actual))
        functions.append(dict(name=name, address=address, stock_size=size,
                              candidate_size=len(actual), byte_exact=actual == expected,
                              expected_sha256=sha(expected), actual_sha256=sha(actual)))
    provenance = dict(stock_sha256=sha(stock), stock_md5=STOCK_MD5,
                      partial_report=str(report_path), partial_report_sha256=sha(report_blob),
                      linked_elf=str(elf_path), linked_elf_sha256=sha(elf_blob),
                      source_sha256=report['source_sha256'], functions=functions,
                      compiler=report['compiler'], compiler_sha256=report['compiler_sha256'],
                      flags=report['flags'], checker_sha256=sha(Path(__file__).read_bytes()))
    return expected_code, actual_code, provenance


def execute(code, seed, caches, sets, ways):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    for base, size in ((0, 0x10000), (FLASH, 0x10000),
                       (0x24000000, 0x10000), (STOP, 0x1000)):
        cpu.mem_map(base, size)
    for address, blob in code:
        cpu.mem_write(address, blob)
    rng = random.Random(seed)
    registers = {address: rng.getrandbits(32)
                 for address in (CCR, SHCSR, CCSIDR, CSSELR, CTRL, RNR)}
    registers[CCR] = (registers[CCR] & ~0x30000) | (caches << 16)
    registers[CCSIDR] = (rng.getrandbits(4) << 28) | (sets << 13) | (ways << 3) | 1
    registers[RNR] = rng.randrange(8)
    regions = {i: [rng.getrandbits(32), rng.getrandbits(32)] for i in range(8)}
    initial_ccr, initial_shcsr = registers[CCR], registers[SHCSR]
    cpu.mem_write(SP - 0x100, bytes(rng.getrandbits(8) for _ in range(0x100)))
    cpu.reg_write(UC_ARM_REG_SP, SP)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    trace, helper_entries = [], Counter()
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoded = {}

    def read_register(uc, offset, size, base):
        address = base + offset
        if size != 4:
            raise ValueError('unexpected MMIO read width: %r' % (address, size))
        if address in (RBAR, RASR):
            value = regions[registers[RNR]][int(address == RASR)]
        elif address in registers:
            value = registers[address]
        else:
            raise ValueError('unexpected MMIO read: %#x' % address)
        trace.append(('read', address, size, value))
        return value

    def write_register(uc, offset, size, value, base):
        address = base + offset
        if size != 4 or address not in (CCR, SHCSR, CSSELR, CTRL, RNR, RBAR, RASR,
                                       ICIALLU, DCISW):
            raise ValueError('unexpected MMIO write: %r' % ((address, size, value),))
        if address in (RBAR, RASR):
            # Observed writes have RBAR.VALID clear; do not silently implement
            # other MPU bank-switching behavior that the model does not cover.
            if address == RBAR and value & 0x10:
                raise ValueError('unsupported RBAR.VALID bank switch')
            regions[registers[RNR]][int(address == RASR)] = value
        else:
            if address == RNR and value not in regions:
                raise ValueError('unsupported MPU region: %d' % value)
            registers[address] = value
        trace.append(('write', address, size, value))

    def instruction(uc, address, size, _):
        if address in MOCKS:
            trace.append(('call', MOCKS[address]))
            uc.reg_write(UC_ARM_REG_R0, 0xa5a5a5a5)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            return
        if not any(start <= address and address + size <= start + len(blob)
                   for start, blob in code):
            raise ValueError('execution left audited functions at %#x' % address)
        if address in (0x08001f88, 0x08001fd8, 0x08001ff0):
            helper_entries[address] += 1
        if address not in decoded:
            insn = next(decoder.disasm(bytes(uc.mem_read(address, size)), address), None)
            if insn is None or insn.size != size:
                raise ValueError('cannot decode instruction at %#x' % address)
            decoded[address] = (insn.mnemonic, insn.op_str)
        mnemonic, operands = decoded[address]
        if mnemonic in ('dmb', 'dsb', 'isb'):
            trace.append(('barrier', mnemonic, operands))

    cpu.mmio_map(0xe000e000, 0x2000, read_register, 0xe000e000,
                 write_register, 0xe000e000)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    try:
        cpu.emu_start(ENTRY | 1, STOP, count=1000000)
    except UcError as error:
        raise ValueError('emulation failed at %#x; last events %r' %
                         (cpu.reg_read(UC_ARM_REG_PC), trace[-8:])) from error
    if (cpu.reg_read(UC_ARM_REG_PC) != STOP or cpu.reg_read(UC_ARM_REG_R0) != 0 or
            cpu.reg_read(UC_ARM_REG_SP) != SP):
        raise ValueError('board_main did not return zero with its stack restored')
    if helper_entries != {0x08001f88: 2, 0x08001fd8: 2, 0x08001ff0: 1}:
        raise ValueError('actual MPU helpers were not called as expected')
    if [t[1] for t in trace if t[0] == 'call'] != ['gd_jscope_init', 'sched_main']:
        raise ValueError('external handoff order differs')
    if (registers[CCR] != initial_ccr | 0x30000 or registers[CTRL] != 5 or
            registers[SHCSR] != initial_shcsr | 0x10000 or
            regions[0] != [0, 0x1000873f] or regions[1] != [0x24000000, 0x03060011]):
        raise ValueError('unexpected final MPU/cache register state')
    invalidations = sum(t[0] == 'write' and t[1] == DCISW for t in trace)
    if invalidations != (0 if caches & 1 else (sets + 1) * (ways + 1)):
        raise ValueError('unexpected D-cache invalidation count')
    return dict(trace=trace, registers=registers, regions=regions,
                helper_entries=helper_entries, outcome='returned_zero')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-partial/results.json')
    parser.add_argument('--elf', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-board-mmio.json')
    args = parser.parse_args()
    expected_code, actual_code, report = load_inputs(args.partial_report, args.elf)
    report.update(scope='board_main and actual MPU helpers: modeled MMIO/barriers only',
                  whole_image_verified=False, actual_hardware_verified=False,
                  mocked_calls={hex(k): v for k, v in MOCKS.items()},
                  limitations=['No real board boot, interrupts, MPU permission enforcement, '
                               'or cache contents/timing are modeled.',
                               'CCSIDR and unrelated register bits are deterministic samples; '
                               'external debug and scheduler bodies are not executed.'],
                  trace_cases=[])
    for seed in (0, 17, 0x4757):
        for caches in range(4):
            for sets, ways in ((0, 0), (0, 3), (1, 0), (3, 1), (127, 3), (511, 3)):
                case = dict(seed=seed, cache_enable_bits=caches,
                            ccsidr_sets_encoding=sets, ccsidr_ways_encoding=ways)
                try:
                    expected = execute(expected_code, seed, caches, sets, ways)
                    actual = execute(actual_code, seed, caches, sets, ways)
                    case['trace_exact'] = expected == actual
                    trace = actual['trace']
                    case.update(outcome=actual['outcome'], events=len(trace),
                                mmio_accesses=sum(t[0] in ('read', 'write') for t in trace),
                                barriers=sum(t[0] == 'barrier' for t in trace),
                                trace_sha256=sha(json.dumps(trace).encode()),
                                trace=trace)
                    if expected != actual:
                        case['stock_execution'] = expected
                        case['candidate_execution'] = actual
                        case['first_different_event'] = next(
                            (i for i, (a, b) in enumerate(zip(expected['trace'], trace)) if a != b),
                            min(len(expected['trace']), len(trace)))
                except ValueError as error:
                    case.update(trace_exact=False, error=str(error))
                report['trace_cases'].append(case)
    # Detect edits/rebuilds during execution; never certify a stale linked image.
    source_freshness(report['source_sha256'])
    if (sha(Path(report['linked_elf']).read_bytes()) != report['linked_elf_sha256'] or
            sha(args.partial_report.read_bytes()) != report['partial_report_sha256']):
        raise ValueError('partial build changed during emulation; rerun against a stable build')
    report['all_trace_cases_exact'] = all(c['trace_exact'] for c in report['trace_cases'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    passed = sum(c['trace_exact'] for c in report['trace_cases'])
    print('%d/%d modeled MMIO/barrier cases EXACT; actual MPU helpers, two mocked handoffs' %
          (passed, len(report['trace_cases'])))
    print('This is not a board boot test or binary-equivalence gate. Report: ' + str(args.out))
    for case in report['trace_cases']:
        if not case['trace_exact']:
            print('First failure: ' + json.dumps({k: v for k, v in case.items()
                  if k not in ('trace', 'stock_execution', 'candidate_execution')}))
            break
    return 0 if report['all_trace_cases_exact'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        sys.exit('board MMIO check failed: ' + str(error))
