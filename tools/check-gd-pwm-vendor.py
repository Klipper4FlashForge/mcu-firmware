#!/usr/bin/env python3
"""Complete motor PWM and signed-current function/code-pool gate."""
from gd_function_gate import main

UNITS = {'pwm_vendor': ('mclib_pwm_vendor.c', []),
         'pwm_channel': ('mclib_pwm_vendor.c', ['PWM_CHANNEL']),
         }
CASES = [('mclib_current_acquisition_set_polarity', 0x3a60, 4),
         ('mclib_current_acquisition_read', 0x3a68, 112),
         ('mclib_pwm_enable', 0x3b08, 48),
         ('mclib_pwm_channel_init', 0x3c20, 98),
         ('mclib_pwm_init', 0x3c88, 116),
         ]
CASE_UNITS = {name: 'pwm_channel' if name == 'mclib_pwm_channel_init' else 'pwm_vendor'
              for name, _, _ in CASES}
SYMBOLS = {name: address | 1 for name, address, _ in CASES}
SYMBOLS.update({'timer_channel_output_state_config': 0x4e39,
    'timer_deinit': 0x4f29, 'timer_struct_para_init': 0x5851,
    'timer_init': 0x5139, 'timer_channel_output_struct_para_init': 0x4eb9,
    'timer_channel_output_config': 0x4a11, 'timer_channel_output_mode_config': 0x4d49,
    'timer_channel_output_shadow_config': 0x4dd9, 'timer_channel_output_pulse_value_config': 0x4db1,
    'timer_channel_composite_pwm_mode_config': 0x49f9, 'timer_channel_additional_output_shadow_config': 0x4991,
    'timer_channel_additional_compare_value_config': 0x4981,
    'timer_primary_output_config': 0x5569})


def self_test():
    """Bounded register-latch/call-ABI model, not motor hardware validation."""
    import hashlib
    import json
    import random
    import struct
    import sys
    from gd_function_gate import ROOT
    from elftools.elf.elffile import ELFFile
    sys.path.insert(0, str(ROOT / 'work/python-deps'))
    from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE)
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                  UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
    out = ROOT / 'work/mainBoardGD-pwm-vendor'
    report_path = out / 'results.json'
    report = json.loads(report_path.read_text())
    sha = lambda b: hashlib.sha256(b).hexdigest()
    for name, expected in report['source_sha256'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('stale source: ' + name)
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    assert hashlib.md5(stock).hexdigest() == report['stock_md5']
    bodies, hashes = {}, {}
    for row in report['results']:
        path = out / (row['name'] + '.elf')
        hashes[str(path.relative_to(ROOT))] = sha(path.read_bytes())
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            section = elf.get_section_by_name('.text')
            assert section['sh_addr'] == row['address']
            assert sha(section.data()) == row['actual_sha256']
            assert sha(stock[0x4418 + row['address']:0x4418 + row['address']
                             + row['expected_size']]) == row['expected_sha256']
            symbol = elf.get_section_by_name('.symtab').get_symbol_by_name(row['name'])[0]
            assert symbol['st_value'] & ~1 == row['address']
            bodies[row['name']] = section.data()
    config, stack, stop = 0x24000000, 0x2400f000, 0x10000000
    rng = random.Random(0x3c884990)
    regs = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)
    cases = {name: (address, size) for name, address, size in CASES}
    call_addresses = {value & ~1: name for name, value in SYMBOLS.items()}
    # Only these two defaults routines execute as dependencies; other SDK
    # calls are recorded and returned, with configuration payloads captured.
    defaults = ((0x5850, 20), (0x4eb8, 10))

    def run(name, body, args, parameter, registers):
        address, _ = cases[name]
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for base, size in ((0, 0x10000), (config, 0x10000),
                           (0x40010000, 0x10000), (stop, 0x1000)):
            cpu.mem_map(base, size)
        cpu.mem_write(0, stock[0x4418:0x4418 + 28120])
        cpu.mem_write(address, body)
        cpu.mem_write(config, parameter)
        cpu.mem_write(stack - 128, bytes([0xa5]) * 144)
        for target, value in registers.items():
            cpu.mem_write(target, struct.pack('<I', value))
        trace = []

        def memory(machine, access, target, size, value, _):
            if 0x40010000 <= target < 0x40020000:
                if access != UC_MEM_WRITE:
                    value = int.from_bytes(machine.mem_read(target, size), 'little')
                trace.append(('write' if access == UC_MEM_WRITE else 'read',
                              target, size, value))

        def instruction(machine, pc, size, _):
            if address <= pc < address + len(body) or pc == stop:
                return
            if any(start <= pc < start + length for start, length in defaults):
                return
            if pc not in call_addresses:
                raise AssertionError(f'unexpected code {pc:#x}')
            values = [machine.reg_read(reg) for reg in regs]
            if pc == 0x5138:
                item = (pc, values[0], bytes(machine.mem_read(values[1], 24)).hex())
            elif pc == 0x4a10:
                item = (pc, *values[:2], bytes(machine.mem_read(values[2], 12)).hex())
            elif pc in (0x4f28,):
                item = (pc, values[0])
            elif pc in (0x3c20, 0x5568):
                item = (pc, *values[:2])
            else:
                item = (pc, *values)
            trace.append(item)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory)
        cpu.hook_add(UC_HOOK_CODE, instruction)
        for reg, value in zip(regs, args):
            cpu.reg_write(reg, value)
        cpu.reg_write(UC_ARM_REG_SP, stack)
        cpu.reg_write(UC_ARM_REG_LR, stop | 1)
        cpu.emu_start(address | 1, stop, count=2000)
        assert cpu.reg_read(UC_ARM_REG_PC) == stop
        assert cpu.reg_read(UC_ARM_REG_SP) == stack
        assert bytes(cpu.mem_read(stack, 16)) == bytes([0xa5]) * 16
        return (trace, bytes(cpu.mem_read(config, len(parameter))),
                {target: bytes(cpu.mem_read(target, 4)) for target in registers})

    counts = {}

    def check(name, args, parameter=bytes([0xa5]) * 48):
        registers = {0x40010000 + offset: rng.getrandbits(32)
                     for offset in range(0, 0x100, 4)}
        address, size = cases[name]
        expected = run(name, stock[0x4418 + address:0x4418 + address + size],
                       args, parameter, registers)
        actual = run(name, bodies[name], args, parameter, registers)
        assert actual == expected, (name, args, expected, actual)
        counts[name] = counts.get(name, 0) + 1

    check('timer_channel_output_struct_para_init', [config])
    for polarity in range(256):
        check('mclib_current_acquisition_set_polarity', [config, polarity])
    for timer in (0x40010000, 0x40010400, 0x40010800, 0x40011000):
        for period in (0, 1, 7500, 0x80000000, 0xffffffff):
            for channels in ((0, 1, 2, 3), (16, 17, 18, 19), (255, 0, 4, 20)):
                parameter = struct.pack('<II4B', timer, period, *channels)
                check('mclib_pwm_init', [config], parameter)
                check('mclib_pwm_enable', [config], parameter)
                for channel in channels:
                    check('mclib_pwm_channel_init', [config, channel], parameter)
    for channel in (*range(21), 31, 32, 255, 0xffffffff):
        for value in (0, 1, 2, 0x100, 0xffffffff):
            for name in ('timer_channel_additional_output_shadow_config', 'timer_channel_additional_compare_value_config'):
                check(name, [0x40010000, channel, value])
            # C's unchecked shift is only claimed for defined shifts 0..31.
            if channel < 32:
                check('timer_channel_composite_pwm_mode_config', [0x40010000, channel, value])
    for value in (0, 1, 2, 0x8000, 0xffffffff):
        check('timer_primary_output_config', [0x40010000, value])
    result = dict(scope='ordered register-latch and mocked SDK call/config ABI; not hardware',
                  excluded=['current read is byte-exact; floating-point model not run',
                            'unchecked shift inputs >=32 not given portable C semantics'],
                  source_sha256=report['source_sha256'], stock_sha256=sha(stock),
                  isolated_report_sha256=sha(report_path.read_bytes()), elf_sha256=hashes,
                  checker_sha256=sha((ROOT / 'tools/check-gd-pwm-vendor.py').read_bytes()),
                  cases=counts, passed=sum(counts.values()))
    result_path = ROOT / 'work/mainBoardGD-pwm-vendor-model.json'
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{sum(counts.values())} ordered MMIO/call/configuration cases passed: {result_path}')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--self-test']:
        self_test()
    else:
        raise SystemExit(main('pwm-vendor', CASES, UNITS, CASE_UNITS, SYMBOLS))
