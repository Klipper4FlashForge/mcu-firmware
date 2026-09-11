#!/usr/bin/env python3
"""Bounded motor-reset comparison with actual stock callees, never mocks.

Checks motor/acquisition/PWM state, ordered state/MMIO accesses, call arguments,
callee-saved registers, SP and return PC. Final LR is recorded separately:
it is caller-clobbered and differs for the candidate's tail call.
"""
import argparse
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
import unicorn
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M7, UC_ARM_REG_C1_C0_2,
    UC_ARM_REG_FPEXC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R4, UC_ARM_REG_D8, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

FLASH, ENTRY, STOCK_SIZE, NEXT = 0x08000000, 0x080011b0, 110, 0x08001220
MOTOR, ACQ, PWM, TIMER = 0x24010020, 0x24011000, 0x24011100, 0x40010000
STACK, STOP = 0x2401ff00, 0x10000000
NAME = 'mclib_motor_reset'
MD5 = 'fb64911bac422a27d7ed7fab3597603f'
# Real callees and bridge code allowed during execution, with complete extents.
SPANS = [(0x08002c48, 14), (0x08002148, 10), (0x08003198, 10),
         (0x080031ca, 10), (0x3ad8, 48), (0x39e0, 50),
         (0x4e38, 126), (0x5bee, 10), (0x08000b28, 12)]
CALLS = {0x08002c48: ('observer_reset', 1), 0x08002148: ('pi_reset', 1),
         0x3ad8: ('pwm_disable', 1), 0x39e0: ('acquisition_reset', 1),
         0x4e38: ('channel_enable', 3), 0x08000b28: ('filter_init', 3)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs(path):
    blob = path.read_bytes()
    report = json.loads(blob)
    for filename, digest in report['source_sha256'].items():
        if sha((ROOT / filename).read_bytes()) != digest:
            raise ValueError('stale source: ' + filename)
    if sha(Path(report['compiler']).read_bytes()) != report['compiler_sha256']:
        raise ValueError('compiler changed')
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    if hashlib.md5(stock).hexdigest() != MD5 or report['stock_md5'] != MD5:
        raise ValueError('wrong stock image')
    rows = [r for r in report['results'] if r['name'] == NAME]
    if len(rows) != 1:
        raise ValueError('missing/ambiguous reset row')
    row = rows[0]
    elf_path = path.parent / (NAME + '.elf')
    elf_blob = elf_path.read_bytes()
    elf = ELFFile(io.BytesIO(elf_blob))
    section = elf.get_section_by_name('.text')
    symbol = elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    code = section.data()
    expected = stock[ENTRY - FLASH:ENTRY - FLASH + STOCK_SIZE]
    if (row['address'] != ENTRY or row['expected_size'] != STOCK_SIZE
            or section['sh_addr'] != ENTRY or len(symbol) != 1
            or symbol[0]['st_value'] & ~1 != ENTRY
            or symbol[0]['st_info']['type'] != 'STT_FUNC'
            or len(code) != row['actual_size'] or ENTRY + len(code) > NEXT
            or sha(code) != row['candidate_sha256']
            or sha(expected) != row['expected_sha256']
            or stock[0x121e:0x1220] != b'\0\0'):
        raise ValueError('reset span, real entry, next-entry bound or hash differs')
    callees = []
    for address, size in SPANS:
        offset = address - FLASH if address >= FLASH else address + 0x4418
        callees.append(dict(address=address, size=size, sha256=sha(stock[offset:offset + size])))
    return stock, expected, code, dict(isolated_report=str(path), isolated_report_sha256=sha(blob),
        elf_sha256={str(elf_path): sha(elf_blob)}, source_sha256=report['source_sha256'],
        compiler=report['compiler'], compiler_sha256=report['compiler_sha256'], flags=report['flags'],
        stock_md5=MD5, stock_sha256=sha(stock), actual_stock_callees=callees,
        checker_sha256=sha(Path(__file__).read_bytes()), unicorn_version=unicorn.__version__)


class Runner:
    def __init__(self, stock, code):
        self.c = c = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        for address, size in [(FLASH, 0x10000), (0, 0x10000), (0x24000000, 0x20000),
                              (TIMER, 0x1000), (STOP, 0x1000)]:
            c.mem_map(address, size)
        c.mem_write(FLASH, stock)
        c.mem_write(0, stock[0x4418:])
        c.mem_write(ENTRY, code)
        c.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        c.reg_write(UC_ARM_REG_FPEXC, 1 << 30)

        def instruction(cpu, address, size, _):
            if not any(base <= address and address + size <= base + extent
                       for base, extent in [(ENTRY, len(code)), *SPANS]):
                raise ValueError('execution left audited graph at %#x' % address)
            if address in CALLS:
                name, nargs = CALLS[address]
                regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2]
                self.calls.append((name, tuple(cpu.reg_read(r) for r in regs[:nargs])))

        def access(cpu, kind, address, size, value, _):
            for name, base, extent in [('motor', MOTOR, 792), ('acquisition', ACQ, 48),
                                      ('pwm', PWM, 12), ('timer', TIMER, 256)]:
                if base <= address and address + size <= base + extent:
                    if kind == UC_MEM_WRITE or name == 'timer':
                        if kind != UC_MEM_WRITE:
                            value = int.from_bytes(cpu.mem_read(address, size), 'little')
                        self.accesses.append((name, 'write' if kind == UC_MEM_WRITE else 'read',
                                              address - base, size, value))
                    return
            if STACK - 240 <= address and address + size <= STACK:
                return
            if kind != UC_MEM_WRITE and (address < 0x10000 or FLASH <= address < FLASH + 0x10000):
                return
            raise ValueError('unexpected data access at %#x' % address)
        c.hook_add(UC_HOOK_CODE, instruction)
        c.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, access)

    def run(self, motor, acquisition, pwm, timer):
        c = self.c
        self.accesses, self.calls = [], []
        for address, data in [(MOTOR, motor), (ACQ, acquisition), (PWM, pwm), (TIMER, timer)]:
            c.mem_write(address, data)
        c.mem_write(STACK - 256, b'\x6d' * 272)
        saved = {UC_ARM_REG_R4 + i: 0x10203040 + i for i in range(8)}
        saved.update({UC_ARM_REG_D8 + i: 0x1122334455667700 + i for i in range(8)})
        for reg, value in saved.items():
            c.reg_write(reg, value)
        c.reg_write(UC_ARM_REG_R0, MOTOR)
        c.reg_write(UC_ARM_REG_SP, STACK)
        c.reg_write(UC_ARM_REG_LR, STOP | 1)
        c.emu_start(ENTRY | 1, STOP, count=5000)
        if c.reg_read(UC_ARM_REG_PC) != STOP or c.reg_read(UC_ARM_REG_SP) != STACK:
            raise ValueError('reset did not restore SP/return PC')
        if any(c.reg_read(reg) != value for reg, value in saved.items()):
            raise ValueError('callee-saved integer/FP state changed')
        if (bytes(c.mem_read(STACK - 256, 16)) != b'\x6d' * 16
                or bytes(c.mem_read(STACK, 16)) != b'\x6d' * 16):
            raise ValueError('stack guard changed')
        state = tuple(bytes(c.mem_read(base, size)) for base, size in
                      [(MOTOR, 792), (ACQ, 48), (PWM, 12), (TIMER, 256)])
        return state, self.accesses, self.calls, c.reg_read(UC_ARM_REG_LR)


def expected_state(motor, acquisition, pwm, timer):
    m, a, t = bytearray(motor), bytearray(acquisition), bytearray(timer)
    for offset, width, value in [(0xce, 1, 0), (0xd2, 1, 0), (0xd0, 1, 1),
            (0xd1, 1, 0), (0x98, 1, 0), (0x60, 4, 0), (0x68, 2, 0x2000),
            (0x6a, 2, 0x4000), (0x70, 2, 0), (0xcc, 1, 0), (0x8c, 4, 0x7f281500)]:
        m[offset:offset + width] = value.to_bytes(width, 'little')
    for offset in [0xf0 + i for i in (0x40, 0x24, 0x28, 0x34, 0x38)] + [
            base + i for base in (0x284, 0x2b0, 0x2dc) for i in (0x1c, 0x24, 0x28)]:
        m[offset:offset + 4] = b'\0' * 4
    a[0x1c:0x20] = struct.pack('<HH', 8192, 8192)
    a[0x14], a[0x16:0x18] = 1, b'\0\0'
    for offset in (0x20, 0x28):
        # Stock filter initialization stores (sample << shift) - sample.
        a[offset:offset + 6] = struct.pack('<IH', (8192 << 8) - 8192, 8)
    mask = {0: 1, 1: 0x10, 2: 0x100, 3: 0x1000, 16: 4, 17: 0x40, 18: 0x400, 19: 0x4000}
    value = int.from_bytes(t[0x20:0x24], 'little')
    for channel in pwm[8:12]:
        value &= ~mask.get(channel, 0)
    t[0x20:0x24] = value.to_bytes(4, 'little')
    return bytes(m), bytes(a), pwm, bytes(t)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report', type=Path, default=ROOT / 'work/mainBoardGD-motor/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-motor-reset-model.json')
    args = parser.parse_args()
    stock, expected, candidate, report = inputs(args.isolated_report.resolve())
    old, new = Runner(stock, expected), Runner(stock, candidate)
    rng, digest, lr_pairs, count = random.Random(0x52455345), hashlib.sha256(), set(), 0
    channels = [[0, 1, 2, 3], [16, 17, 18, 19], [0, 16, 3, 19], [255, 4, 15, 20]]
    channels += [[channel] * 4 for channel in range(256)]
    for seed in range(4):
        for selected in channels:
            m, a, p, t = bytearray(rng.randbytes(792)), rng.randbytes(48), bytearray(rng.randbytes(12)), rng.randbytes(256)
            m[0x310:0x318] = struct.pack('<II', ACQ, PWM)
            p[:4], p[8:12] = struct.pack('<I', TIMER), bytes(selected)
            inputs_ = bytes(m), a, bytes(p), t
            before, after = old.run(*inputs_), new.run(*inputs_)
            if before[:3] != after[:3] or after[0] != expected_state(*inputs_):
                raise ValueError('state/ordered writes/MMIO/call mismatch: ' + repr((seed, selected)))
            lr_pairs.add((before[3], after[3]))
            digest.update(repr((sha(bytes(m)), selected, after[:3])).encode())
            count += 1
    report.update(scope='isolated motor reset with real stock callees; no mocked calls',
        whole_image_verified=False, results=[dict(name=NAME, cases=count, passed=count,
        expected_size=len(expected), actual_size=len(candidate), next_entry=NEXT,
        byte_exact=expected == candidate, final_lr_pairs=sorted(lr_pairs), result_sha256=digest.hexdigest())],
        limitations=['Callees execute actual stock code, not a combined candidate implementation.',
            'Timer MMIO uses ordinary register latches, without peripheral timing or interrupts.',
            'Sequential traces do not prove asynchronous interrupt/publication timing.',
            'LR is caller-clobbered: tail-call and BL-return paths can leave different LR values; SP and return PC must match.',
            'Bounded initialized valid pointers/channel cases, not malformed-pointer safety or whole firmware boot.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{NAME}: {count}/{count} state/ordered-write/MMIO/call/ABI cases PASS; final LR pairs {sorted(lr_pairs)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
