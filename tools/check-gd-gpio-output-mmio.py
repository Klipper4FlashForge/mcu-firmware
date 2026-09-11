#!/usr/bin/env python3
"""Compare GPIO output/input setup ARM behavior against stock in Unicorn.

Consumes isolated check-gd-gpio-output.py ELFs without rebuilding or truncating
oversized candidates. GPIO register read/write order, motor handoff arguments,
interrupt calls, setup results and inhibit-byte accesses are compared. External
GPIO clock/peripheral/reset setup calls and motor bodies are mocked explicitly.
This finite MMIO model is not a hardware test or a binary-equivalence gate.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import random
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS,
                     UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_PC,
                               UC_ARM_REG_LR, UC_CPU_ARM_CORTEX_M7)
from scatterload import entries, decompress, HELPERS

STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
MD5 = 'fb64911bac422a27d7ed7fab3597603f'
FLASH, ITCM_OFFSET, RAM = 0x08000000, 0x4418, 0x24000000
PORTS, INHIBIT, RETURN, STACK, STOP = RAM + 0x21c4, RAM + 0x8b38, RAM + 0x9000, RAM + 0xf000, 0x10000000
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
CASES = [('gpio_in_setup', 0x30f0, 104), ('gpio_out_reset', 0x31b0, 264),
         ('gpio_out_setup', 0x32b8, 104), ('gpio_out_toggle_noirq', 0x3320, 266),
         ('gpio_out_write', 0x3430, 846)]
MOCKS = {0x3080: ('gpio_clock', 1), 0x37c8: ('gpio_peripheral', 3),
         0x31b0: ('gpio_out_reset', 4), 0x38a0: ('irq_save', 0),
         0x3898: ('irq_restore', 1), 0x2420: ('lookup_shutdown_string', 1),
         0x4410: ('shutdown', 1), 0x5b9e: ('motor_direction', 2),
         0x5ba8: ('motor_step', 1), 0x5bb2: ('motor_disable', 1),
         0x5bbc: ('motor_enable', 1)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def freshness(hashes):
    for name, expected in hashes.items():
        path = ROOT / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise ValueError('source changed; rerun check-gd-gpio-output.py: ' + name)


def load(build):
    report_blob = (build / 'results.json').read_bytes()
    gate = json.loads(report_blob)
    hashes = gate['source_sha256']
    required = {str(ROOT / 'mcu/mainBoardGD/recovered/gpio_output.c'),
                str(ROOT / 'mcu/mainBoardGD/recovered/gpio.h')}
    if not required <= {str((ROOT / p).resolve()) for p in hashes}:
        raise ValueError('gate report lacks GPIO source/header provenance')
    freshness(hashes)
    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != MD5 or gate['stock_md5'] != MD5:
        raise ValueError('wrong stock address profile')
    data_regions = [(src, size) for src, dst, size, fn in entries(stock, FLASH, 0x3744)
                    if dst == RAM and HELPERS.get(stock[fn-FLASH:fn-FLASH+8]) == 'decompress']
    if len(data_regions) != 1:
        raise ValueError('missing stock RAM initialization')
    source, size = data_regions[0]
    initialized, _ = decompress(stock[source-FLASH:], size)
    if len(initialized) != size:
        raise ValueError('wrong decompressed RAM length')
    ports = struct.unpack_from('<10I', initialized, PORTS - RAM)
    if ports != tuple(0 if n == 8 else 0x58020000 + n * 0x400 for n in range(10)):
        raise ValueError('unexpected GPIO port table')
    blobs, evidence = {}, []
    for name, address, span in CASES:
        rows = [r for r in gate['results'] if r['name'] == name]
        if len(rows) != 1:
            raise ValueError('missing/ambiguous gate row: ' + name)
        row = rows[0]
        path = build / (name + '.elf')
        elf_blob = path.read_bytes()
        section = ELFFile(io.BytesIO(elf_blob)).get_section_by_name('.text')
        actual = section.data()
        expected = stock[ITCM_OFFSET + address:ITCM_OFFSET + address + span]
        if (section['sh_addr'] != address or row['address'] != address or
                row['expected_size'] != span or row['actual_size'] != len(actual) or
                sha(actual) != row['actual_sha256'] or sha(expected) != row['expected_sha256']):
            raise ValueError('ELF/stock no longer agrees with gate: ' + name)
        blobs[name] = expected, actual
        evidence.append(dict(name=name, elf=str(path), elf_sha256=sha(elf_blob),
                             address=address, stock_size=span, actual_size=len(actual),
                             expected_sha256=sha(expected), actual_sha256=sha(actual),
                             byte_exact=expected == actual))
    return blobs, initialized, dict(stock_sha256=sha(stock), stock_md5=MD5,
        gate_report=str(build / 'results.json'), gate_report_sha256=sha(report_blob),
        source_sha256=hashes, compiler=gate['compiler'], flags=gate['flags'],
        compiler_sha256=gate['compiler_sha256'], functions=evidence,
        checker_sha256=sha(Path(__file__).read_bytes()))


def execute(name, address, code, initialized, pin, value, inhibit, high, seed):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
    for base, size in ((0, 0x10000), (RAM, 0x10000), (STOP, 0x1000)):
        cpu.mem_map(base, size)
    cpu.mem_write(address, code)
    cpu.mem_write(RAM, initialized)
    cpu.mem_write(INHIBIT, bytes(inhibit))
    rng = random.Random(seed)
    cpu.mem_write(RETURN, bytes([0xa5]) * 12)
    cpu.mem_write(STACK - 0x100, bytes(rng.getrandbits(8) for _ in range(0x100)))
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    bit = 1 << (pin & 15)
    # Direct write/toggle accept an arbitrary byte tag with a valid physical
    # handle. Reset needs a constructible tag; its separate port lookup is not
    # validated by the firmware itself.
    regs = 0x58020000 + ((pin // 16) % 8) * 0x400
    if name == 'gpio_out_reset':
        regs = struct.unpack('<I', cpu.mem_read(PORTS + (pin // 16) * 4, 4))[0]
    args = (RETURN, pin, value) if name.endswith('_setup') else (pin | 0xa5b6c700, regs, bit, value)
    for register, val in zip(REGS, args):
        cpu.reg_write(register, val)
    registers = {0x58020000 + port * 0x400 + off: rng.getrandbits(32)
                 for port in range(10) for off in range(0, 0x30, 4)}
    registers[regs + 0x14] = (registers[regs + 0x14] & ~bit) | (bit if high else 0)
    trace, outcome = [], ['returned']

    def mmio_read(uc, offset, size, base):
        target = base + offset
        if size != 4 or target not in registers:
            raise ValueError('unexpected GPIO read: %r' % ((target, size),))
        result = registers[target]
        trace.append(('read', target, size, result))
        return result

    def mmio_write(uc, offset, size, val, base):
        target = base + offset
        if size != 4 or target not in registers:
            raise ValueError('unexpected GPIO write: %r' % ((target, size),))
        trace.append(('write', target, size, val))
        registers[target] = val
        port_base = target & ~0x3ff
        reg_offset = target - port_base
        if reg_offset == 0x18:
            registers[port_base + 0x14] = ((registers[port_base + 0x14] | (val & 0xffff))
                                           & ~(val >> 16))
        elif reg_offset == 0x28:
            registers[port_base + 0x14] &= ~val
        elif reg_offset == 0x2c:
            registers[port_base + 0x14] ^= val

    def ram_read(uc, access, target, size, val, _):
        if target < INHIBIT + 2 and target + size > INHIBIT:
            trace.append(('inhibit_read', target, size, int.from_bytes(uc.mem_read(target, size), 'little')))

    def ram_write(uc, access, target, size, val, _):
        if target < INHIBIT + 2 and target + size > INHIBIT:
            trace.append(('inhibit_write', target, size, val))

    def instruction(uc, pc, size, _):
        if pc in MOCKS and pc != address:
            call, nargs = MOCKS[pc]
            values = [uc.reg_read(r) for r in REGS[:nargs]]
            if call == 'gpio_out_reset':
                values[0] &= 255  # the three padding bytes are not pin value
            if call == 'lookup_shutdown_string':
                start = values[0]
                if not address <= start < address + len(code):
                    raise ValueError('shutdown string outside audited function pool')
                values = [bytes(uc.mem_read(start, address + len(code) - start)).split(b'\0')[0].decode()]
            trace.append(('call', call, *values))
            if call == 'shutdown':
                outcome[0] = 'shutdown'
                uc.emu_stop()
                return
            uc.reg_write(UC_ARM_REG_R0, (seed & 1) if call == 'irq_save' else
                         123 if call == 'lookup_shutdown_string' else 0xa5a5a5a5)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif not address <= pc < address + len(code):
            raise ValueError('unexpected code dependency at %#x' % pc)

    cpu.mmio_map(0x58020000, 0x3000, mmio_read, 0x58020000, mmio_write, 0x58020000)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_READ, ram_read, begin=INHIBIT, end=INHIBIT+1)
    cpu.hook_add(UC_HOOK_MEM_WRITE, ram_write, begin=INHIBIT, end=INHIBIT+1)
    try:
        cpu.emu_start(address | 1, STOP, count=10000)
    except UcError as error:
        raise ValueError('emulation failed PC=%#x after %r' %
                         (cpu.reg_read(UC_ARM_REG_PC), trace[-8:])) from error
    if outcome[0] == 'returned' and (cpu.reg_read(UC_ARM_REG_PC) != STOP or
                                   cpu.reg_read(UC_ARM_REG_SP) != STACK):
        raise ValueError('function failed to return with restored stack')
    result = dict(outcome=outcome[0], trace=trace, registers=registers,
                  inhibit=list(cpu.mem_read(INHIBIT, 2)))
    if name.endswith('_setup') and outcome[0] == 'returned':
        raw = bytes(cpu.mem_read(RETURN, 12))
        result['handle'] = [raw[0], *struct.unpack_from('<2I', raw, 4)]
    return result


def scenarios(name):
    values = (0, 1, 256, 0x80000000)
    patterns = ((0, 0), (1, 0), (0, 1), (255, 128))
    if name.endswith('_setup'):
        for pin in (*range(256), 256, 257, 0x10090, 0xffffffff):
            for value in (*values, 128, 255, 0xffffffff) if name == 'gpio_in_setup' else values:
                yield pin, value, (0, 0), 0, pin ^ value
    elif name == 'gpio_out_reset':
        for pin in range(160):
            if 128 <= pin < 144:
                continue
            for value in values:
                for high in (0, 1):
                    yield pin, value, patterns[high], high, pin ^ value ^ high
    elif name == 'gpio_out_write':
        for pin in range(256):
            for value in values:
                for pattern in patterns:
                    yield pin, value, pattern, 0, pin ^ value
    else:
        for pin in range(256):
            for high in (0, 1):
                for pattern in patterns:
                    yield pin, 0, pattern, high, pin ^ high


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'work/mainBoardGD-gpio-output')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-gpio-output-mmio.json')
    args = parser.parse_args()
    blobs, initialized, report = load(args.build)
    report.update(scope='isolated GPIO ARM MMIO and ABI model; not hardware/binary identity',
                  whole_image_verified=False, actual_hardware_verified=False,
                  mocked_calls={hex(pc): call for pc, (call, _) in MOCKS.items()},
                  limitations=['Setup rejects invalid pins; direct reset tested only for 144 constructible handles.',
                               'Direct write/toggle use all 256 byte tags with valid supplied physical handles.',
                               'Motor and clock/peripheral bodies are mocked; setup mocks its out-of-line reset.',
                               'Setup result padding is unspecified and ignored. MMIO has no interrupt/timing model.'],
                  results=[])
    all_exact = True
    for name, address, _ in CASES:
        count, passed, events, digest, failures = 0, 0, Counter(), hashlib.sha256(), []
        for pin, value, inhibit, high, seed in scenarios(name):
            inputs = dict(pin=pin, value=value, inhibit=inhibit, initial_output_high=high, seed=seed)
            count += 1
            try:
                expected = execute(name, address, blobs[name][0], initialized, pin, value, inhibit, high, seed)
                actual = execute(name, address, blobs[name][1], initialized, pin, value, inhibit, high, seed)
                exact = actual == expected
                digest.update(json.dumps([inputs, actual], sort_keys=True).encode())
                events.update(t[0] for t in actual['trace'])
                if not exact and len(failures) < 4:
                    failures.append(dict(inputs=inputs, stock=expected, candidate=actual))
            except ValueError as error:
                exact = False
                if len(failures) < 4:
                    failures.append(dict(inputs=inputs, error=str(error)))
            passed += exact
        all_exact &= passed == count
        report['results'].append(dict(name=name, cases=count, passing_cases=passed,
                                      trace_exact=passed == count, event_counts=events,
                                      execution_digest=digest.hexdigest(), first_failures=failures))
        print('%s: %d/%d cases %s' % (name, passed, count, 'EXACT' if passed == count else 'DIFF'), flush=True)
    freshness(report['source_sha256'])
    if sha((args.build / 'results.json').read_bytes()) != report['gate_report_sha256']:
        raise ValueError('gate report changed while running; rerun')
    for fn in report['functions']:
        if sha(Path(fn['elf']).read_bytes()) != fn['elf_sha256']:
            raise ValueError('isolated ELF changed while running: ' + fn['name'])
    report['all_trace_cases_exact'] = all_exact
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print('Modeled traces only, not code equality. Report: ' + str(args.out))
    return int(not all_exact)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as error:
        sys.exit('GPIO MMIO check failed: ' + str(error))
