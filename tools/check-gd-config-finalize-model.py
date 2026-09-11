#!/usr/bin/env python3
"""Stock/candidate finalize allocation effects; external services are modeled."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
    UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from elftools.elf.elffile import ELFFile


def main():
    digest = lambda data: hashlib.sha256(data).hexdigest()
    out = ROOT / 'work/mainBoardGD-config-finalize'
    report_path = out / 'results.json'
    report = json.loads(report_path.read_text())
    for filename, expected in report['source_sha256'].items():
        assert digest((ROOT / filename).read_bytes()) == expected, 'stale source: ' + filename
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    assert hashlib.md5(stock).hexdigest() == report['stock_md5']
    row = report['results'][0]
    elf_path = out / 'command_finalize_config.elf'
    with elf_path.open('rb') as stream:
        elf = ELFFile(stream)
        section = elf.get_section_by_name('.text')
        body = section.data()
        entry = elf.get_section_by_name('.symtab').get_symbol_by_name(row['name'])[0]['st_value'] & ~1
        assert section['sh_addr'] == row['address'] == entry == row['actual_symbol_address']
        assert digest(body) == row['actual_sha256']
    stock_body = stock[0x4418 + row['address']:0x4418 + row['address'] + row['expected_size']]
    assert digest(stock_body) == row['expected_sha256']
    saved = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
             UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]
    ram, heap, stack, stop, args = 0x24000000, 0x24010000, 0x24031000, 0x10000000, 0x24030000

    def run(code, stride, available, finalized, second_limit):
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        uc.mem_map(0, 0x10000)
        uc.mem_map(ram, 0x33000)
        uc.mem_map(stop, 0x1000)
        uc.mem_write(0, stock[0x4418:0x4418 + 28120])
        uc.mem_write(entry, code)
        uc.mem_write(heap, bytes([0xa5]) * 0x18000)
        uc.mem_write(stack - 256, bytes([0xa5]) * 272)
        def word(address, value):
            uc.mem_write(address, struct.pack('<I', value))
        word(0x24003810, heap)
        word(0x24003818, 0x87654321)
        uc.mem_write(0x2400881e, struct.pack('<H', finalized))
        word(0x24008820, 0)
        uc.mem_write(0x24008824, bytes([stride]))
        word(0x24008828, 0)
        word(args, 0x12345678)
        calls, strings, reason = [], {}, []
        ends = iter((heap + available, heap + second_limit))

        def instruction(machine, pc, size, _):
            r0, r1 = machine.reg_read(UC_ARM_REG_R0), machine.reg_read(UC_ARM_REG_R1)
            if pc == 0x2d78:
                value = next(ends)
                calls.append(('dynmem_end', value))
                machine.reg_write(UC_ARM_REG_R0, value)
            elif pc == 0x5b44:
                assert heap <= r0 <= heap + 0x18000 and 0 <= r1 <= 0x18000
                calls.append(('memclr', r0, r1))
                if r1:
                    machine.mem_write(r0, bytes(r1))
            elif pc == 0x2420:
                message = bytes(machine.mem_read(r0, 80)).split(b'\0')[0].decode()
                calls.append(('lookup', message))
                strings[17] = message
                machine.reg_write(UC_ARM_REG_R0, 17)
            elif pc == 0x4410:
                reason.append(strings[r0])
                machine.emu_stop()
                return
            elif entry <= pc < entry + len(code):
                return
            else:
                raise AssertionError(f'unexpected code {pc:#x}')
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        uc.hook_add(UC_HOOK_CODE, instruction)
        uc.reg_write(UC_ARM_REG_R0, args)
        uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, stop | 1)
        for i, register in enumerate(saved):
            uc.reg_write(register, 0x76540000 + i)
        uc.emu_start(entry | 1, stop, count=100000)
        if not reason:
            assert uc.reg_read(UC_ARM_REG_PC) == stop
            assert uc.reg_read(UC_ARM_REG_SP) == stack
            assert all(uc.reg_read(register) == 0x76540000 + i for i, register in enumerate(saved))
        assert bytes(uc.mem_read(stack - 256, 128)) == bytes([0xa5]) * 128
        assert bytes(uc.mem_read(stack, 16)) == bytes([0xa5]) * 16
        state = [bytes(uc.mem_read(address, size)) for address, size in (
            (0x24003810, 12), (0x2400881e, 14), (heap, 0x18000), (args, 4))]
        return calls, reason, state

    cases = []
    for stride in (0, 1, 3, 4, 5, 12, 64, 255):
        width = max(stride, 4)
        for available in (0, width - 1, width, width + 1, 2 * width,
                          7 * width + 3, 1023 * width, 1024 * width, 1025 * width):
            # Keep this bounded model's heap below the dedicated argument area.
            if available > 0x18000:
                continue
            for finalized, second_limit in ((0, available), (0, 0), (1, available), (65535, available)):
                case = (stride, available, finalized, second_limit)
                assert run(stock_body, *case) == run(body, *case), case
                cases.append(case)
    result = dict(scope='bounded final RAM/call/ABI comparison; dynmem_end, lookup, shutdown and memclr mocked; not boot or byte equality',
                  exact=True, cases=len(cases), inputs=cases,
                  source_report_sha256=digest(report_path.read_bytes()),
                  candidate_elf_sha256=digest(elf_path.read_bytes()),
                  model_sha256=digest(Path(__file__).read_bytes()))
    path = ROOT / 'work/mainBoardGD-config-finalize-model.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(cases)}/{len(cases)} final-state/call/ABI cases pass; external services mocked')


if __name__ == '__main__':
    main()
