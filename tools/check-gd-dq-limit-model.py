#!/usr/bin/env python3
"""Compare isolated DQ limiters using the actual stock square-root callee.

This validates neither reconstructed mclib_sqrt_positive nor the integrated
motor loop. It compares Unicorn's floating-point behavior, not physical M7
exception/timing behavior. No callee is replaced with a host function/mock.
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
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M7, UC_ARM_REG_C1_C0_2,
                               UC_ARM_REG_FPEXC, UC_ARM_REG_FPSCR,
                               UC_ARM_REG_R0, UC_ARM_REG_R4, UC_ARM_REG_D8,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

FLASH, MOTOR, STACK, STOP = 0x08000000, 0x24000000, 0x2400ff00, 0x10000000
ENTRY, EXTENT, SQRT, SQRT_SIZE = FLASH + 0x15e0, 144, FLASH + 0x2df8, 28
NAME = 'mclib_limit_dq_voltage'
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def inputs(path):
    report_blob = path.read_bytes()
    report = json.loads(report_blob)
    for name, digest in report['source_sha256'].items():
        source = ROOT / name
        if not source.is_file() or sha(source.read_bytes()) != digest:
            raise ValueError('stale isolated source report: ' + name)
    compiler = Path(report['compiler'])
    if sha(compiler.read_bytes()) != report['compiler_sha256']:
        raise ValueError('isolated compiler changed')
    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != STOCK_MD5 or report['stock_md5'] != STOCK_MD5:
        raise ValueError('wrong stock image')
    rows = [row for row in report['results'] if row['name'] == NAME]
    if len(rows) != 1:
        raise ValueError('missing/ambiguous DQ report row')
    row = rows[0]
    elf_path = path.parent / (NAME + '.elf')
    elf_blob = elf_path.read_bytes()
    elf = ELFFile(io.BytesIO(elf_blob))
    section = elf.get_section_by_name('.text')
    symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    candidate = section.data()
    expected = stock[ENTRY - FLASH:ENTRY - FLASH + EXTENT]
    if (row['address'] != ENTRY or row['expected_size'] != EXTENT
            or section['sh_addr'] != ENTRY or len(symbols) != 1
            or symbols[0]['st_info']['type'] != 'STT_FUNC'
            or symbols[0]['st_value'] & ~1 != ENTRY
            or row['actual_symbol_address'] != ENTRY or not row['entry_exact']
            or not 0 < len(candidate) <= EXTENT
            or len(candidate) != row['actual_size']
            or sha(candidate) != row['actual_sha256']
            or sha(expected) != row['expected_sha256']):
        raise ValueError('ELF/stock extent, entry or digest differs from report')
    provenance = dict(
        isolated_report=str(path), isolated_report_sha256=sha(report_blob),
        elf_sha256={str(elf_path): sha(elf_blob)},
        source_sha256=report['source_sha256'], compiler=str(compiler),
        compiler_sha256=report['compiler_sha256'], flags=report['flags'],
        stock_md5=STOCK_MD5, stock_sha256=sha(stock),
        checker_sha256=sha(Path(__file__).read_bytes()), unicorn_version=unicorn.__version__,
        stock_callee=dict(name='mclib_sqrt_positive', address=SQRT, size=SQRT_SIZE,
                          sha256=sha(stock[SQRT - FLASH:SQRT - FLASH + SQRT_SIZE]),
                          implementation='actual stock instructions, not reconstructed C or mock'))
    return stock, expected, candidate, provenance


class Runner:
    def __init__(self, stock, code):
        self.cpu = c = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        for address, size in [(FLASH, 0x10000), (MOTOR, 0x10000), (STOP, 0x1000)]:
            c.mem_map(address, size)
        c.mem_write(FLASH, stock)
        c.mem_write(ENTRY, code)
        c.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        c.reg_write(UC_ARM_REG_FPEXC, 1 << 30)

        def guard(cpu, address, size, _):
            if not (ENTRY <= address and address + size <= ENTRY + len(code)
                    or SQRT <= address and address + size <= SQRT + SQRT_SIZE):
                raise ValueError('execution left audited limiter/callee at %#x' % address)
            if address == SQRT:
                self.sqrt_calls += 1
        c.hook_add(UC_HOOK_CODE, guard)

    def run(self, d, q, fpscr):
        c = self.cpu
        self.sqrt_calls = 0
        before = bytearray(b'\xa5' * 792)
        before[64:72] = struct.pack('<II', d, q)
        c.mem_write(MOTOR, bytes(before))
        c.mem_write(STACK - 256, b'\x6d' * 272)
        saved = {UC_ARM_REG_R4 + i: 0x12345670 + i for i in range(8)}
        saved.update({UC_ARM_REG_D8 + i: 0x1122334455667700 + i for i in range(8)})
        for register, value in saved.items():
            c.reg_write(register, value)
        c.reg_write(UC_ARM_REG_FPSCR, fpscr)
        c.reg_write(UC_ARM_REG_R0, MOTOR)
        c.reg_write(UC_ARM_REG_SP, STACK)
        c.reg_write(UC_ARM_REG_LR, STOP | 1)
        c.emu_start(ENTRY | 1, STOP, count=500)
        if c.reg_read(UC_ARM_REG_PC) != STOP or c.reg_read(UC_ARM_REG_SP) != STACK:
            raise ValueError('incorrect limiter return PC/SP')
        if not all(c.reg_read(k) == v for k, v in saved.items()):
            raise ValueError('limiter corrupted callee-saved integer/FP registers')
        if (bytes(c.mem_read(STACK - 256, 16)) != b'\x6d' * 16
                or bytes(c.mem_read(STACK, 16)) != b'\x6d' * 16):
            raise ValueError('limiter crossed stack guard')
        after = bytes(c.mem_read(MOTOR, 792))
        if after[:64] != before[:64] or after[72:] != before[72:]:
            raise ValueError('limiter changed motor fields outside D/Q voltage')
        return after[64:72], c.reg_read(UC_ARM_REG_FPSCR), self.sqrt_calls


def pairs():
    # Signed zeros, subnormal boundaries, +/-1, neighboring D-clamp values,
    # largest finite values, infinities and quiet/signaling NaN payloads.
    values = [0, 0x80000000, 1, 0x80000001, 0x007fffff, 0x807fffff,
              0x00800000, 0x80800000, 0x3f800000, 0xbf800000,
              0x41bfeb84, 0x41bfeb85, 0x41bfeb86,
              0xc1bfeb84, 0xc1bfeb85, 0xc1bfeb86,
              0x7f7fffff, 0xff7fffff, 0x7f800000, 0xff800000,
              0x7fc00000, 0xffc12345, 0x7f800001, 0xff812345]
    rng = random.Random(0x44514c49)
    return ([(d, q) for d in values for q in values]
            + [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-math/results.json')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'work/mainBoardGD-dq-limit-model.json')
    args = parser.parse_args()
    stock, expected, candidate, report = inputs(args.isolated_report.resolve())
    a, b = Runner(stock, expected), Runner(stock, candidate)
    count, sqrt_calls, digest = 0, 0, hashlib.sha256()
    cases = pairs()
    for mode in range(16):
        # Four rounding modes crossed with FZ/DN off/on; exception flags clear.
        fpscr = (mode & 3) << 22 | (mode >> 2) << 24
        for d, q in cases:
            old, new = a.run(d, q, fpscr), b.run(d, q, fpscr)
            if old != new:
                raise ValueError('DQ/FPSCR/callee disagreement: ' + repr(
                    (hex(d), hex(q), hex(fpscr), old, new)))
            digest.update(struct.pack('<III', d, q, fpscr) + new[0]
                          + struct.pack('<II', new[1], new[2]))
            count += 1
            sqrt_calls += new[2]
    report.update(
        scope='isolated DQ limiter equivalence using actual stock sqrt callee',
        whole_image_verified=False,
        results=[dict(name=NAME, cases=count, passed=count, stock_entry=ENTRY,
                      candidate_entry=ENTRY, expected_size=len(expected),
                      actual_size=len(candidate), byte_exact=expected == candidate,
                      actual_stock_sqrt_calls=sqrt_calls, result_sha256=digest.hexdigest())],
        limitations=[
            'Unicorn FP model, not physical Cortex-M7 exception or timing validation.',
            'The square-root dependency executes stock instructions; reconstructed mclib_sqrt_positive is validated separately by its byte gate and sqrt model.',
            'Finite deterministic sample, not exhaustive 32-bit floating-point inputs.',
            'No asynchronous motor-state changes, complete motor-loop or firmware boot validation.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{NAME}: {count}/{count} DQ/FPSCR/ABI cases PASS; '
          f'{sqrt_calls} actual stock sqrt calls.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
