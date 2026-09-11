#!/usr/bin/env python3
"""Compare PI update state, ordered writes, FP/FPSCR and ABI against stock.

Actual isolated ARM bodies execute in Unicorn; no math operation or callee is
mocked. This is bounded synchronous model evidence, not hardware timing or
whole-firmware validation.
"""
import argparse
import hashlib, io, json, random, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
ENTRY, RAM, STOP, STACK = 0x080020d0, 0x24000000, 0x10000000, 0x2400ff00
EXTENT, NAME = 116, 'mclib_pi_step'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inputs(report_path):
    blob = report_path.read_bytes()
    report = json.loads(blob)
    for filename, expected in report['source_sha256'].items():
        if sha((ROOT / filename).read_bytes()) != expected:
            raise ValueError('stale source: ' + filename)
    compiler = Path(report['compiler'])
    if sha(compiler.read_bytes()) != report['compiler_sha256']:
        raise ValueError('compiler differs from canonical report')
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    if hashlib.md5(stock).hexdigest() != STOCK_MD5 or report['stock_md5'] != STOCK_MD5:
        raise ValueError('unexpected stock image')
    rows = [row for row in report['results'] if row['name'] == NAME]
    if len(rows) != 1:
        raise ValueError('missing or ambiguous PI row')
    row = rows[0]
    path = report_path.parent / (NAME + '.elf')
    elf_blob = path.read_bytes()
    elf = ELFFile(io.BytesIO(elf_blob))
    section = elf.get_section_by_name('.text')
    symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    candidate = section.data()
    expected = stock[ENTRY - 0x08000000:ENTRY - 0x08000000 + EXTENT]
    if (len(symbols) != 1 or symbols[0]['st_info']['type'] != 'STT_FUNC'
            or symbols[0]['st_value'] != ENTRY | 1
            or symbols[0]['st_size'] != len(candidate)
            or elf.header['e_entry'] != ENTRY | 1
            or section['sh_addr'] != ENTRY or row['address'] != ENTRY
            or row['expected_size'] != EXTENT
            or not 0 < len(candidate) <= EXTENT
            or row['actual_size'] != len(candidate)
            or row['candidate_sha256'] != sha(candidate)
            or row['expected_sha256'] != sha(expected)):
        raise ValueError('PI extent, entry, ELF or stock digest mismatch')
    provenance = dict(
        isolated_report=str(report_path), isolated_report_sha256=sha(blob),
        elf_sha256={str(path): sha(elf_blob)},
        source_sha256=report['source_sha256'], compiler=str(compiler),
        compiler_sha256=report['compiler_sha256'], flags=report['flags'],
        stock_md5=STOCK_MD5, stock_sha256=sha(stock),
        expected_sha256=sha(expected), candidate_sha256=sha(candidate),
        checker_sha256=sha(Path(__file__).read_bytes()),
        unicorn_version=unicorn.__version__)
    return expected, candidate, provenance

class Runner:
    def __init__(self, data):
        self.cpu = c = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        c.mem_map(0x08000000, 0x10000)
        c.mem_map(RAM, 0x10000)
        c.mem_map(STOP, 0x1000)
        c.mem_write(ENTRY, data)
        c.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        c.reg_write(UC_ARM_REG_FPEXC, 1 << 30)
        def guard(cpu, address, size, _):
            assert ENTRY <= address and address + size <= ENTRY + len(data), hex(address)
        def write(cpu, access, address, size, value, _):
            if RAM <= address < RAM + 44:
                assert address + size <= RAM + 44
                self.writes.append((address-RAM, size, value))
            else:
                assert STACK - 240 <= address and address + size <= STACK
        def read(cpu, access, address, size, value, _):
            if RAM <= address and address + size <= RAM + 44:
                key = (address-RAM, size)
                self.reads[key] = self.reads.get(key, 0) + 1
            else:
                assert STACK - 240 <= address and address + size <= STACK
        c.hook_add(UC_HOOK_CODE, guard)
        c.hook_add(UC_HOOK_MEM_WRITE, write)
        c.hook_add(UC_HOOK_MEM_READ, read)
    def run(self, fields, mode):
        c = self.cpu
        self.writes = []
        self.reads = {}
        # target, measured, kp, ki, Imax, Imin, Omax, Omin, integral
        target, measured, kp, ki, imax, imin, omax, omin, integral = fields
        initial = struct.pack('<11I', kp, ki, 0xa5a5a5a5, imax, imin, omax, omin,
                              integral, 0xb6b6b6b6, 0xc7c7c7c7, 0xd8d8d8d8)
        c.mem_write(RAM, initial)
        c.mem_write(STACK - 256, b'\x6d' * 272)
        saved = {UC_ARM_REG_R4+i: 0x11223300+i for i in range(8)}
        saved.update({UC_ARM_REG_D8+i: 0x1122334455667700+i for i in range(8)})
        for reg,value in saved.items(): c.reg_write(reg,value)
        c.reg_write(UC_ARM_REG_R0, RAM)
        c.reg_write(UC_ARM_REG_S0, target)
        c.reg_write(UC_ARM_REG_S1, measured)
        c.reg_write(UC_ARM_REG_FPSCR, mode)
        c.reg_write(UC_ARM_REG_SP, STACK)
        c.reg_write(UC_ARM_REG_LR, STOP|1)
        c.emu_start(ENTRY|1, STOP, count=100)
        assert c.reg_read(UC_ARM_REG_PC)==STOP and c.reg_read(UC_ARM_REG_SP)==STACK
        assert all(c.reg_read(reg)==value for reg,value in saved.items())
        assert bytes(c.mem_read(STACK - 256, 16)) == b'\x6d' * 16
        assert bytes(c.mem_read(STACK, 16)) == b'\x6d' * 16
        after=bytes(c.mem_read(RAM,44))
        assert after[:28]==initial[:28] and after[32:36]==initial[32:36]
        # Stock loads the old accumulator and reloads the clamped state.
        # Compare access counts, not full ordering: other loads still move.
        assert self.reads.get((28, 4)) == 2, self.reads
        reads = sorted((offset, size, count) for (offset, size), count in self.reads.items())
        return after.hex(), c.reg_read(UC_ARM_REG_S0), c.reg_read(UC_ARM_REG_FPSCR), self.writes, reads
def cases():
    special=[0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
         0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,
         0x7fc00000,0xffc12345,0x7f800001,0xff812345]
    result=[]
    baseline=[0x3f800000,0,0x3f000000,0x3e000000,0x41200000,0xc1200000,0x41a00000,0xc1a00000,0x3f000000]
    for index in range(9):
        for value in special:
            fields=baseline.copy(); fields[index]=value; result.append(fields)
    # Exercise multiple NaN payloads and opposing infinities concurrently.
    for left in range(9):
        for right in range(left+1,9):
            for a in special[-6:]:
                for b in special[-6:]:
                    fields=baseline.copy(); fields[left]=a; fields[right]=b; result.append(fields)
    rng=random.Random(0x50495354)
    result += [[rng.getrandbits(32) for _ in range(9)] for _ in range(2048)]
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-motor/results.json')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'work/mainBoardGD-pi-model.json')
    args = parser.parse_args()
    expected, candidate, report = inputs(args.isolated_report.resolve())
    a,b=Runner(expected),Runner(candidate)
    count, digest = 0, hashlib.sha256()
    vectors = cases()
    for setting in range(16):
        fpscr=(setting&3)<<22 | (setting>>2)<<24
        for values in vectors:
            old,new=a.run(values,fpscr),b.run(values,fpscr)
            if old != new:
                raise ValueError('PI disagreement: ' + repr(
                    (count, [hex(x) for x in values], hex(fpscr), old, new)))
            digest.update(struct.pack('<10I', *values, fpscr))
            digest.update(json.dumps(new, separators=(',', ':')).encode())
            count+=1
    report.update(
        scope='isolated PI update stock-versus-candidate state/FP/ABI model',
        whole_image_verified=False,
        results=[dict(name=NAME, cases=count, passed=count,
                      stock_entry=ENTRY, candidate_entry=ENTRY,
                      expected_size=len(expected), actual_size=len(candidate),
                      byte_exact=expected == candidate,
                      result_sha256=digest.hexdigest())],
        limitations=[
            'Actual ARM instructions execute in Unicorn; no calls or FP operations are mocked.',
            'Finite deterministic inputs, not exhaustive 32-bit FP or parameter combinations.',
            'Compares complete final FPSCR; exercises four rounding modes and FZ/DN combinations, not physical Cortex-M7 exception/timing validation.',
            'All state data-read counts are compared, including two accumulator reads; full read scheduling and asynchronous controller-state changes are not modeled.',
            'No complete control-loop or firmware boot equivalence is established.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{NAME}: {count}/{count} state/ordered-write/read-count/output/FPSCR/ABI cases PASS.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
