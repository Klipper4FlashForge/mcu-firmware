#!/usr/bin/env python3
"""Full timer SDK function spans, with jump tables but without alignment gaps."""
from gd_function_gate import main, ROOT

# Retired 2026-09-11: every span is GigaDevice's own gd32h7xx_timer.c now
# (check-gd-sdk.py); the hand timer_vendor.c is gone.
PROFILE = []
CASES = [(name, address, size) for name, address, size, _ in PROFILE]
UNITS = {'timer_vendor_' + macro.lower(): ('timer_vendor.c', ['GD_TIMER_' + macro])
         for *_, macro in PROFILE}
CASE_UNITS = {name: 'timer_vendor_' + macro.lower() for name, _, _, macro in PROFILE}
SYMBOLS = {'rcu_periph_reset_enable': 0x5b31,
           'rcu_periph_reset_disable': 0x5b3b}
# The offset table is the compiler's switch lookup table for oc_pulse, not a
# named object: the fourth field names its input section.
DATA_UNITS = {}
DATA_CASES = []
DATA_CASE_UNITS = {}

def self_test():
    """Bounded stock-versus-candidate ordered MMIO/configuration/call model."""
    import hashlib
    import json
    import random
    import struct
    import sys
    sys.path.insert(0, str(ROOT / 'work/python-deps'))
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE, UC_MEM_WRITE
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                  UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                                  UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
                                  UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_SP,
                                  UC_ARM_REG_LR, UC_ARM_REG_PC)
    from elftools.elf.elffile import ELFFile
    out = ROOT / 'work/mainBoardGD-timer-vendor'
    report_path = out / 'results.json'
    report = json.loads(report_path.read_text())
    digest = lambda data: hashlib.sha256(data).hexdigest()
    for name, expected in report['source_sha256'].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError('stale isolated report: ' + name)
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    assert hashlib.md5(stock).hexdigest() == report['stock_md5']
    candidates, elf_hashes = {}, {}
    for row in report['results']:
        filename = out / (row['name'] + '.elf')
        elf_hashes[str(filename)] = digest(filename.read_bytes())
        with filename.open('rb') as stream:
            elf = ELFFile(stream)
            section = elf.get_section_by_name('.text')
            body = section.data()
            entry = elf.get_section_by_name('.symtab').get_symbol_by_name(row['name'])[0]['st_value'] & ~1
            assert digest(body) == row['actual_sha256']
            assert section['sh_addr'] == row['address']
            assert entry == row['actual_symbol_address']
            expected = stock[0x4418 + row['address']:0x4418 + row['address'] + row['expected_size']]
            assert digest(expected) == row['expected_sha256']
            candidates[row['name']] = (row['address'], entry, body)
    preserved = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                 UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]
    config, stack, stop = 0x24000000, 0x24011000, 0x10000000

    def run(address, entry, body, args, registers, parameter):
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for base, size in [(0, 0x10000), (0x40000000, 0x20000),
                           (0x58000000, 0x1000), (config, 0x1000),
                           (stack - 0x1000, 0x2000), (stop, 0x1000)]:
            uc.mem_map(base, size)
        uc.mem_write(0, stock[0x4418:0x4418 + 28120])
        uc.mem_write(address, body)
        uc.mem_write(config, parameter)
        for target, value in registers.items():
            uc.mem_write(target, struct.pack('<I', value))
        uc.mem_write(stack - 256, bytes([0xa5]) * 272)
        trace = []

        def memory(machine, access, target, size, value, _):
            if 0x40000000 <= target < 0x40020000 or 0x58000000 <= target < 0x58001000:
                reading = access != UC_MEM_WRITE
                value = int.from_bytes(machine.mem_read(target, size), 'little') if reading else value
                trace.append(('read' if reading else 'write', target, size, value))
            elif not (config <= target and target + size <= config + len(parameter)
                      or stack - 128 <= target and target + size <= stack
                      or access != UC_MEM_WRITE and (
                          0x5cb8 <= target and target + size <= 0x5d08
                          or address <= target and target + size <= address + len(body))):
                raise AssertionError(f'unexpected data access {target:#x}/{size}')

        def instruction(machine, pc, size, _):
            if pc in (0x5b30, 0x5b3a):
                trace.append(('call', pc, machine.reg_read(UC_ARM_REG_R0)))
                machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
            elif pc != stop and not address <= pc < address + len(body):
                raise AssertionError(f'unexpected code {pc:#x}')

        uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory)
        uc.hook_add(UC_HOOK_CODE, instruction)
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2), args):
            uc.reg_write(register, value)
        for index, register in enumerate(preserved):
            uc.reg_write(register, 0x12340000 + index)
        uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, stop | 1)
        uc.emu_start(entry | 1, stop, count=100000)
        assert uc.reg_read(UC_ARM_REG_PC) == stop
        assert uc.reg_read(UC_ARM_REG_SP) == stack
        assert all(uc.reg_read(register) == 0x12340000 + i for i, register in enumerate(preserved))
        assert bytes(uc.mem_read(stack - 256, 128)) == bytes([0xa5]) * 128
        assert bytes(uc.mem_read(stack, 16)) == bytes([0xa5]) * 16
        return trace, bytes(uc.mem_read(config, len(parameter)))

    rng = random.Random(0x4a105850)
    timers = [0x40000000, 0x40000400, 0x40000800, 0x40000c00, 0x40001000,
              0x40001400, 0x4000e000, 0x4000e400, 0x4000e800, 0x4000ec00,
              0x4000f000, 0x4000f400, 0x40010000, 0x40010400, 0x40014000,
              0x40014400, 0x40014800, 0x4001d000, 0x4001d400, 0x4001d800,
              0x4001dc00, 0x4001f000, 0x40001800]
    base_registers = {timer + offset: rng.getrandbits(32)
                      for timer in timers for offset in range(0, 256, 4)}
    rows = []

    def check(name, args, registers=base_registers, parameter=bytes([0xa5]) * 24, label=''):
        address, size = next((a, s) for n, a, s in CASES if n == name)
        stock_body = stock[0x4418 + address:0x4418 + address + size]
        expected = run(address, address, stock_body, args, registers, parameter)
        actual = run(*candidates[name], args, registers, parameter)
        if actual != expected:
            for index, pair in enumerate(zip(expected[0], actual[0])):
                if pair[0] != pair[1]:
                    print('First differing access', index, pair)
                    break
            raise AssertionError(f'{name} {args} {label}: trace {len(expected[0])}/{len(actual[0])}, '
                                 f'parameter bytes equal={expected[1] == actual[1]}')
        rows.append(dict(name=name, arguments=args, case=label, accesses=len(actual[0]), exact=True))

    check('timer_struct_para_init', [config, 0, 0])
    for timer in timers:
        check('timer_deinit', [timer, 0, 0])
        for count in (0, 255, 256, 0xffffffff):
            p = struct.pack('<4H2I2HI', 0xfedc, 0xffff, 0xffff, 0xa5a5,
                            0x12345678, 0x87654321, 0xffff, 0xa5a5, count)
            check('timer_init', [timer, config, 0], parameter=p, label=str(count))
        for channel in (0, 1, 2, 3, 4, 19, 0xffffffff):
            check('timer_channel_output_config', [timer, channel, config],
                  parameter=struct.pack('<6H', 0xffff, 0x8004, 0x8002, 0x8008, 0x8100, 0x8200))
    for channel in [*range(21), 0xffffffff]:
        for value in (0, 0x12345678, 0xffffffff):
            for suffix in ('oc_mode', 'oc_shadow', 'oc_pulse'):
                check('gd_motor_timer_' + suffix, [0x40010000, channel, value])
    for value in (0, 1, 0x80, 0xffffffff):
        for suffix in ('master_slave', 'master_output'):
            check('gd_motor_timer_' + suffix, [0x40010000, value, 0])
    patterns = [(0, 0, 0), (0x80008000, 0xffe08000, 0xffe0ffff),
                (0x7fff7fff, 0x1f7fff, 0x1f0000)]
    patterns += [(3 << shift, 0, 0) for shift in (0, 5, 10, 16, 21, 26)]
    patterns += [(0, 3 << shift, 0) for shift in (0, 5, 10, 16)]
    patterns += [(0, 0, 3 << 16)]
    for timer in [*timers, 0, 0xffffffff]:
        for pattern in patterns:
            registers = {0x58000500 + offset + word * 4: value
                         for offset in range(0, 0xc0, 12)
                         for word, value in enumerate(pattern)}
            for source in (0, 0x13, 0xffffffff):
                check('timer_input_trigger_source_select', [timer, source, 0], registers, label=str(pattern))
            for mode in [*range(12), 63, 64, 255, 256, 0xffffffff]:
                check('timer_slave_mode_select', [timer, mode, 0], registers, label=str(pattern))
    output = ROOT / 'work/mainBoardGD-timer-vendor-model.json'
    output.write_text(json.dumps(dict(scope='modeled ordered MMIO and reset-call ABI, not hardware timing',
                                     source_sha256=report['source_sha256'],
                                     isolated_report_sha256=digest(report_path.read_bytes()),
                                     elf_sha256=elf_hashes, stock_sha256=digest(stock), results=rows), indent=2) + '\n')
    print(f'{len(rows)} ordered register/configuration/call/ABI model cases passed: {output}')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--self-test']:
        self_test()
    else:
        raise SystemExit(main('timer-vendor', CASES, UNITS, CASE_UNITS, SYMBOLS))
