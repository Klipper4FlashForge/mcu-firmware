#!/usr/bin/env python3
"""Model the complete sincos body, compiled table, output order and FP state.

This checks mclib_sincos only. The separate mclib_sine body's speculative
quadrant arithmetic is not covered. Nonreturning inputs are bounded checks,
not proofs of infinite execution. Unicorn is not physical Cortex-M7 hardware.
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
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS,
                     UC_HOOK_CODE, UC_HOOK_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M7, UC_ARM_REG_C1_C0_2,
                               UC_ARM_REG_FPEXC, UC_ARM_REG_FPSCR,
                               UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4,
                               UC_ARM_REG_S0, UC_ARM_REG_D8,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

FLASH, ENTRY, EXTENT = 0x08000000, 0x08002970, 480
TABLE, TABLE_SIZE = 0x0800352c, 524
OUTPUT, STACK, STOP = 0x24000040, 0x2400ff00, 0x10000000
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audited_object(path, name, address, size, section_name, stock):
    raw = path.read_bytes()
    report = json.loads(raw)
    for filename, digest in report['source_sha256'].items():
        source = ROOT / filename
        if not source.is_file() or sha(source.read_bytes()) != digest:
            raise ValueError('stale source: ' + filename)
    if sha(Path(report['compiler']).read_bytes()) != report['compiler_sha256']:
        raise ValueError('compiler changed')
    if report['stock_md5'] != STOCK_MD5:
        raise ValueError('wrong report stock image')
    rows = [row for row in report['results'] if row['name'] == name]
    if len(rows) != 1:
        raise ValueError('missing/ambiguous report row: ' + name)
    row = rows[0]
    elf_path = path.parent / (name + '.elf')
    elf_blob = elf_path.read_bytes()
    elf = ELFFile(io.BytesIO(elf_blob))
    section = elf.get_section_by_name(section_name)
    symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(name)
    data = section.data()
    expected = stock[address - FLASH:address - FLASH + size]
    if (row['address'] != address or row['expected_size'] != size
            or section['sh_addr'] != address or len(symbols) != 1
            or symbols[0]['st_value'] & ~1 != address
            or row['actual_symbol_address'] != address or not row['entry_exact']
            or len(data) != row['actual_size'] or not 0 < len(data) <= size
            or sha(data) != row['actual_sha256']
            or sha(expected) != row['expected_sha256']):
        raise ValueError('ELF/stock entry, extent or digest differs: ' + name)
    if section_name == '.rodata':
        if (symbols[0]['st_info']['type'] != 'STT_OBJECT'
                or symbols[0]['st_size'] != size or data != expected):
            raise ValueError('compiled sine table is not a complete exact constant object')
    elif symbols[0]['st_info']['type'] != 'STT_FUNC':
        raise ValueError('candidate must be an actual function')
    provenance = dict(report=str(path), report_sha256=sha(raw),
                      elf=str(elf_path), elf_sha256=sha(elf_blob),
                      source_sha256=report['source_sha256'],
                      compiler=report['compiler'], compiler_sha256=report['compiler_sha256'],
                      flags=report['flags'], expected_sha256=sha(expected), actual_sha256=sha(data))
    return expected, data, provenance


class Runner:
    def __init__(self, stock, code, table):
        self.c = c = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        for address, size in [(FLASH, 0x10000), (0x24000000, 0x10000), (STOP, 0x1000)]:
            c.mem_map(address, size)
        c.mem_write(FLASH, stock)
        c.mem_write(ENTRY, code)
        c.mem_write(TABLE, table)
        c.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        c.reg_write(UC_ARM_REG_FPEXC, 1 << 30)

        def guard(cpu, address, size, _):
            if not ENTRY <= address or address + size > ENTRY + len(code):
                raise ValueError('execution left audited sincos body at %#x' % address)

        def write(cpu, kind, address, size, value, _):
            if OUTPUT <= address and address + size <= OUTPUT + 8:
                self.writes.append((address - OUTPUT, size, value))
            elif not STACK - 240 <= address or address + size > STACK:
                raise ValueError('unexpected write outside outputs/stack at %#x' % address)
        c.hook_add(UC_HOOK_CODE, guard)
        c.hook_add(UC_HOOK_MEM_WRITE, write)

    def run(self, bits, mode, alias):
        c = self.c
        self.writes = []
        c.mem_write(OUTPUT - 16, b'\xa5' * 48)
        c.mem_write(STACK - 256, b'\x6d' * 272)
        saved = {UC_ARM_REG_R4 + i: 0x11223340 + i for i in range(8)}
        saved.update({UC_ARM_REG_D8 + i: 0x1122334455667700 + i for i in range(8)})
        for register, value in saved.items():
            c.reg_write(register, value)
        c.reg_write(UC_ARM_REG_FPSCR, mode)
        c.reg_write(UC_ARM_REG_S0, bits)
        c.reg_write(UC_ARM_REG_R0, OUTPUT)
        c.reg_write(UC_ARM_REG_R1, OUTPUT if alias else OUTPUT + 4)
        c.reg_write(UC_ARM_REG_SP, STACK)
        c.reg_write(UC_ARM_REG_LR, STOP | 1)
        c.emu_start(ENTRY | 1, STOP, count=10000)
        returned = c.reg_read(UC_ARM_REG_PC) == STOP
        after = bytes(c.mem_read(OUTPUT - 16, 48))
        if after[:16] != b'\xa5' * 16 or after[24:] != b'\xa5' * 24:
            raise ValueError('output canary changed')
        if not returned:
            if after != b'\xa5' * 48 or self.writes:
                raise ValueError('nonreturning wrap wrote output')
            return False, None, None, []
        if (c.reg_read(UC_ARM_REG_SP) != STACK
                or not all(c.reg_read(k) == v for k, v in saved.items())):
            raise ValueError('callee-saved FP/integer register or SP changed')
        if (bytes(c.mem_read(STACK - 256, 16)) != b'\x6d' * 16
                or bytes(c.mem_read(STACK, 16)) != b'\x6d' * 16):
            raise ValueError('stack canary changed')
        return True, after[16:24].hex(), c.reg_read(UC_ARM_REG_FPSCR), self.writes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-trig/results.json')
    parser.add_argument('--table-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-trig-data/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-trig-model.json')
    args = parser.parse_args()
    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != STOCK_MD5:
        raise ValueError('wrong stock image')
    expected, candidate, code_proof = audited_object(args.isolated_report.resolve(),
        'mclib_sincos', ENTRY, EXTENT, '.text', stock)
    old_table, new_table, table_proof = audited_object(args.table_report.resolve(),
        'mclib_sine_table', TABLE, TABLE_SIZE, '.rodata', stock)
    if (code_proof['compiler_sha256'] != table_proof['compiler_sha256']
            or code_proof['flags'] != table_proof['flags']):
        raise ValueError('code/table compiler or global flags differ')
    a, b = Runner(stock, expected, old_table), Runner(stock, candidate, new_table)
    values = [0, 0x80000000, 1, 0x80000001, 0x007fffff, 0x807fffff, 0x00800000, 0x80800000]
    for center in [0x3fc90fda, 0x40490fda, 0x4096cbe4, 0x40c90fdb]:
        for offset in range(-3, 4):
            values += [center + offset, (center + offset) | 0x80000000]
    rng = random.Random(0x54524947)
    values += [struct.unpack('<I', struct.pack('<f', rng.uniform(-100, 100)))[0]
               for _ in range(1024)]
    count, digest = 0, hashlib.sha256()
    for m in range(16):
        mode = (m & 3) << 22 | (m >> 2) << 24
        for bits in values:
            for alias in [False, True]:
                old, new = a.run(bits, mode, alias), b.run(bits, mode, alias)
                if old != new or not old[0]:
                    raise ValueError('finite sincos disagreement: ' + repr((bits, mode, alias, old, new)))
                digest.update(repr((bits, mode, alias, new)).encode())
                count += 1
    nonreturn = [0x7fc00000, 0xffc12345, 0x7f800001, 0xff800001,
                0x7f800000, 0xff800000, 0x7f7fffff, 0xff7fffff]
    for bits in nonreturn:
        old, new = a.run(bits, 0, False), b.run(bits, 0, False)
        if old != new or old[0]:
            raise ValueError('bounded wrap disagreement: ' + repr((bits, old, new)))
        digest.update(repr((bits, new)).encode())
    report = dict(scope='isolated mclib_sincos + compiled exact table; not mclib_sine',
        whole_image_verified=False, code_provenance=code_proof, table_provenance=table_proof,
        source_sha256=code_proof['source_sha256'], stock_md5=STOCK_MD5,
        stock_sha256=sha(stock), checker_sha256=sha(Path(__file__).read_bytes()),
        unicorn_version=unicorn.__version__, results=[dict(name='mclib_sincos',
        cases=count + len(nonreturn), passed=count + len(nonreturn), finite_cases=count,
        bounded_nonreturning_cases=len(nonreturn), expected_size=len(expected), actual_size=len(candidate),
        byte_exact=expected == candidate, result_sha256=digest.hexdigest())],
        limitations=[
            'Only mclib_sincos is covered; standalone mclib_sine is not validated.',
            'Finite input samples are signed zero/subnormal/quadrant neighbors and random angles in [-100,100], crossed with16 rounding/FZ/DN modes and aliased/distinct output pointers.',
            'Eight NaN/infinity/huge finite cases run for10000 instructions with no output; this is not an infinite-execution proof or NaN-payload propagation proof.',
            'Output write order and final FPSCR are compared; independent FP instruction timing and table-read ordering are not required equal.',
            'Unicorn FP implementation is not physical Cortex-M7 exception/timing or complete firmware validation.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'mclib_sincos: {count} finite output/write-order/FPSCR/ABI cases PASS; '
          f'{len(nonreturn)} bounded nonreturning cases PASS.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
