#!/usr/bin/env python3
"""Compare the source-built positive-square-root helper with stock in Unicorn.

Checks output bits, complete FPSCR, callee-saved registers, SP and stack guards
for 1,042 special/random inputs in 16 rounding/FZ/DN modes. Sources, compiler,
ELF entry/extent and byte hashes must agree with the isolated math report.
This is bounded emulation, not physical exception/timing or motor-loop proof.
"""
import argparse
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
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M7, UC_ARM_REG_C1_C0_2,
                               UC_ARM_REG_FPEXC, UC_ARM_REG_FPSCR, UC_ARM_REG_S0,
                               UC_ARM_REG_R4, UC_ARM_REG_D8, UC_ARM_REG_SP,
                               UC_ARM_REG_LR, UC_ARM_REG_PC)

NAME, ENTRY, EXTENT = 'mclib_sqrt_positive', 0x08002df8, 28
STACK, STOP = 0x24000800, 0x10000000
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'
SDK_HEADER_SHA256 = '338e79760f692a96d5a3543e37706c6374d9782a3f46ad5a910d49dd8458cd50'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def inputs(path):
    report_blob = path.read_bytes()
    report = json.loads(report_blob)
    sources = report['source_sha256']
    for name, expected in sources.items():
        source = ROOT / name
        if not source.is_file() or sha(source.read_bytes()) != expected:
            raise ValueError('stale isolated source: ' + name)
    required = {'mclib_math.c', 'arm_math_intrinsics.h'}
    if not required <= {Path(name).name for name in sources}:
        raise ValueError('math source/intrinsic dependency absent from report')
    compiler = Path(report['compiler'])
    if sha(compiler.read_bytes()) != report['compiler_sha256']:
        raise ValueError('isolated compiler changed')
    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != STOCK_MD5 or report['stock_md5'] != STOCK_MD5:
        raise ValueError('unexpected stock image')
    rows = [r for r in report['results'] if r['name'] == NAME]
    if len(rows) != 1:
        raise ValueError('missing/ambiguous square-root result')
    row = rows[0]
    elf_path = path.parent / (NAME + '.elf')
    elf_blob = elf_path.read_bytes()
    elf = ELFFile(io.BytesIO(elf_blob))
    section = elf.get_section_by_name('.text')
    symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    if section is None or not symbols or len(symbols) != 1:
        raise ValueError('missing/ambiguous candidate section/symbol')
    candidate = section.data()
    expected = stock[ENTRY - 0x08000000:ENTRY - 0x08000000 + EXTENT]
    if (row['address'] != ENTRY or row['expected_size'] != EXTENT
            or section['sh_addr'] != ENTRY or len(expected) != EXTENT
            or symbols[0]['st_info']['type'] != 'STT_FUNC'
            or symbols[0]['st_value'] & ~1 != ENTRY
            or row['actual_symbol_address'] != ENTRY or not row['entry_exact']
            or not 0 < len(candidate) <= EXTENT
            or row['actual_size'] != len(candidate)
            or sha(candidate) != row['actual_sha256']
            or sha(expected) != row['expected_sha256']):
        raise ValueError('candidate entry/extent/byte provenance mismatch')
    sdk = ROOT / 'work/ac6/AC616/include/math.h'
    sdk_observed = sha(sdk.read_bytes()) if sdk.is_file() else None
    provenance = dict(
        isolated_report=str(path), isolated_report_sha256=sha(report_blob),
        elf_sha256={str(elf_path): sha(elf_blob)}, source_sha256=sources,
        compiler=str(compiler), compiler_sha256=report['compiler_sha256'],
        flags=report['flags'], stock_md5=STOCK_MD5, stock_sha256=sha(stock),
        expected_sha256=sha(expected), candidate_sha256=sha(candidate),
        checker_sha256=sha(Path(__file__).read_bytes()),
        unicorn_version=unicorn.__version__,
        sdk_reference=dict(path=str(sdk), lines='414-435',
                           expected_sha256=SDK_HEADER_SHA256,
                           observed_sha256=sdk_observed,
                           locally_verified=sdk_observed == SDK_HEADER_SHA256,
                           required_to_build_or_model=False))
    return expected, candidate, provenance


class Runner:
    def __init__(self, code):
        self.cpu = c = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        c.mem_map(0x08002000, 0x1000)
        c.mem_write(ENTRY, code)
        c.mem_map(0x24000000, 0x1000)
        c.mem_map(STOP, 0x1000)
        c.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        c.reg_write(UC_ARM_REG_FPEXC, 1 << 30)

        def guard(cpu, address, size, unused):
            if not ENTRY <= address < address + size <= ENTRY + len(code):
                raise ValueError('execution escaped audited helper at %#x' % address)
        c.hook_add(UC_HOOK_CODE, guard)

    def run(self, value, fpscr):
        c = self.cpu
        saved = {UC_ARM_REG_R4 + i: 0x12345670 + i for i in range(8)}
        saved.update({UC_ARM_REG_D8 + i: 0x1122334455667700 + i for i in range(8)})
        for register, bits in saved.items():
            c.reg_write(register, bits)
        c.mem_write(STACK - 128, b'\x6d' * 256)
        c.reg_write(UC_ARM_REG_SP, STACK)
        c.reg_write(UC_ARM_REG_LR, STOP | 1)
        c.reg_write(UC_ARM_REG_S0, value)
        c.reg_write(UC_ARM_REG_FPSCR, fpscr)
        c.emu_start(ENTRY | 1, STOP, count=100)
        if (c.reg_read(UC_ARM_REG_PC) != STOP or c.reg_read(UC_ARM_REG_SP) != STACK
                or any(c.reg_read(r) != v for r, v in saved.items())
                or bytes(c.mem_read(STACK - 128, 256)) != b'\x6d' * 256):
            raise ValueError('return/ABI/stack guard mismatch')
        return c.reg_read(UC_ARM_REG_S0), c.reg_read(UC_ARM_REG_FPSCR)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-math/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-sqrt-model.json')
    args = parser.parse_args()
    expected, candidate, provenance = inputs(args.isolated_report.resolve())
    old, new = Runner(expected), Runner(candidate)
    # Both signs: zeros, unit values, infinities, quiet/signaling NaNs,
    # smallest/largest subnormals, smallest normals and largest finite values.
    values = [0, 0x80000000, 0x3f800000, 0xbf800000, 0x7f800000, 0xff800000,
              0x7fc00001, 0x7f800001, 0xffc12345, 0xff812345, 1, 0x80000001,
              0x007fffff, 0x807fffff, 0x00800000, 0x80800000, 0x7f7fffff, 0xff7fffff]
    seed = 0x2df8
    rng = random.Random(seed)
    values += [rng.getrandbits(32) for unused in range(1024)]
    count, digest = 0, hashlib.sha256()
    for value in values:
        for mode in range(16):
            fpscr = ((mode & 3) << 22) | ((mode >> 2) << 24)
            wanted, actual = old.run(value, fpscr), new.run(value, fpscr)
            if wanted != actual:
                raise ValueError('output/FPSCR mismatch: ' + repr(
                    (hex(value), hex(fpscr), wanted, actual)))
            digest.update(json.dumps([value, fpscr, actual]).encode())
            count += 1
    report = dict(scope='isolated positive square-root output/FPSCR/ABI model',
                  provenance=provenance, seed=seed, passed=count,
                  results=[dict(name=NAME, cases=count, all_exact=True,
                                result_sha256=digest.hexdigest())],
                  limitations=[
                      'Bounded deterministic Unicorn execution, not exhaustive equivalence or physical M7 exception/timing validation.',
                      'No motor-loop or whole-firmware execution is modeled.',
                      'The SDK intrinsic implementation is locally documented; its original application-level spelling remains inferred.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{NAME}: {count}/{count} output/FPSCR/ABI cases PASS')


if __name__ == '__main__':
    main()
