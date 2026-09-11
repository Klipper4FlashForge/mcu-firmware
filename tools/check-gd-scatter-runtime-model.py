#!/usr/bin/env python3
"""Run isolated stock/C scatter helpers on stock data and synthetic regions.

Oversized/aligned candidates execute at their actual isolated ELF entries;
this explicitly does not establish the final runtime ABI/layout or bootability.
No calls are mocked. Copy/zero cases obey the runtime's word-alignment contract.
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
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS,
                     UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                     UC_MEM_WRITE)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                               UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                               UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR,
                               UC_CPU_ARM_CORTEX_M7)
from gd_scatter_compress import compress, CANONICAL_HYPOTHESIS
from scatterload import decompress

FLASH, SOURCE, STOP, STACK = 0x08000000, 0x08010000, 0x10000000, 0x2401ff00
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
MD5 = 'fb64911bac422a27d7ed7fab3597603f'
SAVED_REGISTERS = (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                   UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs(path):
    report_bytes = path.read_bytes()
    report = json.loads(report_bytes)
    for name, digest in report['source_sha256'].items():
        source = ROOT / name
        if not source.is_file() or sha(source.read_bytes()) != digest:
            raise ValueError('stale isolated source profile: ' + name)
    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != MD5:
        raise ValueError('wrong stock image')
    functions = {}
    hashes = {}
    for row in report['results']:
        name, address = row['name'], row['address']
        elf_path = path.parent / (name + '.elf')
        blob = elf_path.read_bytes()
        elf = ELFFile(io.BytesIO(blob))
        section = elf.get_section_by_name('.text')
        symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(name)
        actual = section.data()
        expected = stock[address - FLASH:address - FLASH + row['expected_size']]
        if (section['sh_addr'] != address or len(symbols) != 1
                or symbols[0]['st_value'] & ~1 != row['actual_symbol_address']
                or len(actual) != row['actual_size']
                or sha(actual) != row['actual_sha256']
                or sha(expected) != row['expected_sha256']):
            raise ValueError('ELF/stock comparison profile differs: ' + name)
        functions[name] = (address, expected, row['actual_symbol_address'], actual)
        hashes[str(elf_path)] = sha(blob)
    provenance = dict(isolated_report=str(path), isolated_report_sha256=sha(report_bytes),
                      elf_sha256=hashes, source_sha256=report['source_sha256'],
                      compiler=report['compiler'], flags=report['flags'],
                      stock_sha256=sha(stock), checker_sha256=sha(Path(__file__).read_bytes()),
                      oracle_sha256={name: sha((ROOT / 'tools' / name).read_bytes())
                                     for name in ('gd_scatter_compress.py', 'scatterload.py')},
                      unicorn_version=unicorn.__version__)
    return stock, functions, provenance


class Runner:
    def __init__(self, base, code, entry):
        self.cpu = cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        for address, size in ((FLASH, 0x20000), (0, 0x10000),
                              (0x24000000, 0x20000), (STOP, 0x1000)):
            cpu.mem_map(address, size)
        cpu.mem_write(base, code)
        self.entry, self.trace = entry, []

        def instruction(uc, pc, size, _):
            if not (entry <= pc and pc + size <= base + len(code)):
                raise ValueError('execution left audited helper at %#x' % pc)

        def access(uc, kind, address, size, value, _):
            if SOURCE <= address < SOURCE + self.source_size:
                if kind == UC_MEM_WRITE or address + size > SOURCE + self.source_size:
                    raise ValueError('invalid compressed/copy source access')
                value = int.from_bytes(uc.mem_read(address, size), 'little')
                self.trace.append(('read', 'source', address - SOURCE, size, value))
            elif self.destination - 16 <= address < self.destination + self.capacity + 16:
                if not self.destination <= address or address + size > self.destination + self.capacity:
                    raise ValueError('output crossed guard boundary')
                if kind != UC_MEM_WRITE:
                    value = int.from_bytes(uc.mem_read(address, size), 'little')
                self.trace.append(('write' if kind == UC_MEM_WRITE else 'read',
                                   'destination', address - self.destination, size, value))
            elif not (STACK - 240 <= address and address + size <= STACK):
                raise ValueError('unexpected memory access at %#x' % address)

        cpu.hook_add(UC_HOOK_CODE, instruction)
        cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, access)

    def run(self, name, source, destination, size, expected):
        cpu = self.cpu
        self.destination, self.source_size = destination, len(source)
        self.capacity = max(size, len(expected), 4)
        self.trace = []
        cpu.mem_write(SOURCE, source)
        mapped_start = 0x24000000 if destination >= 0x24000000 else 0
        guard_start = max(mapped_start, destination - 16)
        cpu.mem_write(guard_start, bytes([0xa5]) * (self.capacity + 16 + destination - guard_start))
        cpu.mem_write(STACK - 256, bytes([0x6d]) * 272)
        saved = {register: 0x56789000 + 0x10101 * index
                 for index, register in enumerate(SAVED_REGISTERS)}
        for register, value in saved.items():
            cpu.reg_write(register, value)
        for register, value in ((UC_ARM_REG_R0, SOURCE), (UC_ARM_REG_R1, destination),
                                (UC_ARM_REG_R2, size), (UC_ARM_REG_SP, STACK),
                                (UC_ARM_REG_LR, STOP | 1)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.entry | 1, STOP, count=1000000)
        if cpu.reg_read(UC_ARM_REG_PC) != STOP or cpu.reg_read(UC_ARM_REG_SP) != STACK:
            raise ValueError('runtime helper did not return with restored stack')
        if any(cpu.reg_read(register) != value for register, value in saved.items()):
            raise ValueError('runtime helper corrupted a callee-saved integer register')
        if (cpu.mem_read(STACK - 256, 16) != bytes([0x6d]) * 16
                or cpu.mem_read(STACK, 16) != bytes([0x6d]) * 16):
            raise ValueError('runtime helper crossed a stack canary')
        output = bytes(cpu.mem_read(destination, self.capacity))
        wanted = expected + bytes([0xa5]) * (self.capacity - len(expected))
        if output != wanted:
            raise ValueError('output differs from independent expected data')
        result = cpu.reg_read(UC_ARM_REG_R0) if name == 'gd_runtime_decompress' else None
        if result is not None and result != 0:
            raise ValueError('decompressor did not return zero')
        return self.trace, output, result


def cases(name, stock):
    rng = random.Random(0x53434154)
    if name == 'gd_runtime_decompress':
        expanded, consumed = decompress(stock[0x3778:], 11912)
        yield stock[0x3778:0x3778 + consumed], 0x24000000, 11912, expanded
        for size in (1, 2, 3, 15, 16, 17, 254, 255, 256, 257, 1024, 2048, 4096):
            samples = [bytes(size), bytes(i % 251 for i in range(size)), rng.randbytes(size)]
            for sample in samples:
                encoded = compress(sample, CANONICAL_HYPOTHESIS)
                restored, used = decompress(encoded, len(sample))
                if restored != sample or used != len(encoded):
                    raise ValueError('synthetic compressor/oracle round trip failed')
                yield encoded, 0x24000020, len(sample), sample
        for distance in (255, 256, 511, 512, 767, 768, 1024):
            prefix = rng.randbytes(distance)
            sample = prefix + prefix
            yield compress(sample, CANONICAL_HYPOTHESIS), 0x24000020, len(sample), sample
        # Unlike the host decoder, stock uses a do/while: zero requested output
        # still consumes a token and may produce data. Preserve that behavior.
        yield b'\x01\x00', 0x24000020, 0, b''
        yield b'\x02\x00Q', 0x24000020, 0, b'Q'
    elif name == 'gd_runtime_copy':
        for size in (0, 4, 8, 12, 16, 28, 32, 60, 64, 256, 1024, 28120):
            for destination in (0, 0x24000020):
                source = stock[0x4418:] if size == 28120 else rng.randbytes(max(size, 1))
                yield source, destination, size, source[:size]
    elif name == 'gd_runtime_zero':
        for size in (0, 4, 8, 12, 16, 28, 32, 60, 64, 256, 1024, 33976):
            yield b'Z', 0x24002e88 if size == 33976 else 0x24000020, size, bytes(size)
    else:
        yield b'Z', 0x24000020, 16, b''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-scatter-runtime/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-scatter-runtime-model.json')
    args = parser.parse_args()
    stock, functions, report = inputs(args.isolated_report)
    rows = []
    for name, (base, expected_code, entry, candidate_code) in functions.items():
        expected_runner, actual_runner = Runner(base, expected_code, base), Runner(base, candidate_code, entry)
        count, trace_hash = 0, hashlib.sha256()
        for source, destination, size, expected in cases(name, stock):
            old = expected_runner.run(name, source, destination, size, expected)
            new = actual_runner.run(name, source, destination, size, expected)
            if old != new:
                raise ValueError('stock/C ordered accesses differ: %s case %d' % (name, count))
            trace_hash.update(repr((sha(source), destination, size, new)).encode())
            count += 1
        rows.append(dict(name=name, cases=count, passed=count, trace_sha256=trace_hash.hexdigest(),
                         stock_entry=base, candidate_entry=entry, byte_exact=expected_code == candidate_code))
        print('%s: %d/%d output/access/return cases EXACT' % (name, count, count), flush=True)
    report.update(scope='isolated runtime behavior, not final link or bootability',
                  whole_image_verified=False, results=rows,
                  limitations=['Valid linker streams and aligned word-region sizes only, except explicit zero-output token cases.',
                               'Shifted/oversized candidates execute in isolated mappings, not at final stock entries.',
                               'No malformed stream safety, instruction timing or complete boot validation.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
