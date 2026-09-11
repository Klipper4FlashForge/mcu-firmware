#!/usr/bin/env python3
"""Verify real typed mainBoardGD zero-initialized objects and leave unknown holes.

  python3 tools/check-gd-bss.py

CASES is (symbol, address, size, input_section); ALIASES and SYMBOLS are the
partial-link integration interface. Verification requires actual SHT_NOBITS
sections and exact symbol/section size/alignment, not invented zero byte blobs.
No executable or initialized-flash coverage is claimed by this layout gate.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess

from elftools.elf.elffile import ELFFile
from gd_function_gate import COMPAT
from scatterload import entries, HELPERS

ROOT = Path(__file__).resolve().parents[1]
ZI_START, ZI_SIZE = 0x24002e88, 33976
CASES = [(name, address, size, '.bss.' + name) for name, address, size in [
    ('ff_close_num', 0x24002e88, 4),
    ('gd_jscope_buffer', 0x24002e8c, 1024),
    ('tasks_status', 0x2400328c, 1),
    ('shutdown_status', 0x24003290, 1),
    ('shutdown_reason', 0x24003292, 1),
    ('ff_temp_waketime', 0x24003294, 4),
    ('gd_rtt_control', 0x24003298, 168),
    ('gd_rtt_down_buffer', 0x24003340, 16),
    ('gd_rtt_up_buffer', 0x24003350, 1024),
    ('mclib_acquisition_extruder', 0x24003750, 0x30),
    ('mclib_acquisition_y', 0x24003780, 0x30),
    ('mclib_acquisition_x', 0x240037b0, 0x30),
    ('mclib_acquisition_z', 0x240037e0, 0x30),
    ('alloc_end', 0x24003810, 4),
    ('analog_wake', 0x24003814, 1),
    ('buttons_wake', 0x24003815, 1),
    ('command_sync_state', 0x24003816, 1),
    ('config_crc', 0x24003818, 4),
    ('dynamic_memory', 0x2400381c, 0x5000),
    ('in_sendf', 0x2400881c, 1),
    ('move_count', 0x2400881e, 2),
    ('move_free_list', 0x24008820, 4),
    ('move_item_size', 0x24008824, 1),
    ('move_list', 0x24008828, 4),
    ('oid_count', 0x2400882c, 1),
    ('oids', 0x24008830, 4),
    ('ff_pa_pc', 0x24008834, 4),
    ('ff_pa_action', 0x24008838, 4),
    ('ff_pa_value', 0x2400883c, 4),
    ('mclib_pwm_extruder', 0x24008840, 0x0c),
    ('mclib_pwm_y', 0x2400884c, 0x0c),
    ('mclib_pwm_x', 0x24008858, 0x0c),
    ('mclib_pwm_z', 0x24008864, 0x0c),
    ('receive_buf', 0x24008870, 384),
    ('receive_pos', 0x240089f0, 2),
    ('shutdown_jmp', 0x240089f8, 160),
    ('ff_timer_close', 0x24008a98, 1),
    ('stats_send_time', 0x24008a9c, 4),
    ('stats_send_time_high', 0x24008aa0, 4),
    ('stats_count', 0x24008aa4, 4),
    ('stats_sum', 0x24008aa8, 4),
    ('stats_sumsq', 0x24008aac, 4),
    ('timer_repeat_until', 0x24008ab0, 4),
    ('transmit_buf', 0x24008ab4, 96),
    ('transmit_max', 0x24008b14, 1),
    ('transmit_pos', 0x24008b15, 1),
    ('trsync_wake', 0x24008b16, 1),
    ('gpio_step_inhibit_72', 0x24008b38, 1),
    ('gpio_step_inhibit_73', 0x24008b39, 1),
]]
# The current bindings have distinct addresses: no duplicate allocations or
# speculative aliases are needed. Keep this interface for future proven aliases.
ALIASES, SYMBOLS = {}, {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def holes(cases=CASES):
    cursor, result = ZI_START, []
    for name, address, size, _ in sorted(cases, key=lambda c: c[1]):
        if address < cursor or size <= 0 or address + size > ZI_START + ZI_SIZE:
            raise ValueError('overlapping or out-of-range BSS profile: ' + name)
        if address > cursor:
            result.append(dict(address=cursor, end=address, size=address - cursor,
                               classification='unclassified_zero_initialized_interval'))
        cursor = address + size
    if cursor < ZI_START + ZI_SIZE:
        result.append(dict(address=cursor, end=ZI_START + ZI_SIZE,
                           size=ZI_START + ZI_SIZE - cursor,
                           classification='unclassified_zero_initialized_interval'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('MCU_GD_CC'))
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-bss')
    args = parser.parse_args()
    tc = module('check-gd-toolchain.py')
    cc, out = tc.compiler_path(args.cc), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stock = tc.STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != tc.STOCK_MD5:
        raise ValueError('unsupported stock image')
    zero_records = [r for r in entries(stock, 0x08000000, 0x3744)
                    if HELPERS.get(stock[r[3] - 0x08000000:r[3] - 0x08000000 + 8]) == 'zeroinit']
    if len(zero_records) != 1 or zero_records[0][1:3] != (ZI_START, ZI_SIZE):
        raise ValueError('unexpected stock zero-initialization region')
    unknown = holes()
    source = ROOT / 'mcu/mainBoardGD/recovered/runtime_state.c'
    obj, elf, script, dependencies = [out / name for name in
                                      ('runtime_state.o', 'runtime_state.elf', 'runtime_state.ld', 'runtime_state.d')]
    flags = [*tc.FLAGS, *COMPAT]
    compile_command = [str(cc), *flags, '-MMD', '-MF', str(dependencies),
                       '-MT', 'dependencies', '-c', str(source), '-o', str(obj)]
    subprocess.run(compile_command, check=True)
    script.write_text('SECTIONS {\n' + '\n'.join(
        f' .runtime_bss_{name} 0x{address:x} (NOLOAD) : {{ *({section}) }}'
        for name, address, _, section in CASES) + '\n}\n')
    link_command = [str(cc), *tc.FLAGS[:4], '-nostdlib', '-Wl,--entry=dynamic_memory',
                    '-Wl,-T,' + str(script), str(obj), '-o', str(elf)]
    subprocess.run(link_command, check=True)
    rows = []
    with obj.open('rb') as object_stream, elf.open('rb') as linked_stream:
        object_elf, linked_elf = ELFFile(object_stream), ELFFile(linked_stream)
        symbols = {s.name: s for s in linked_elf.get_section_by_name('.symtab').iter_symbols()}
        actual_sections = {s.name for s in object_elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']}
        expected_sections = {section for _, _, _, section in CASES}
        if actual_sections != expected_sections:
            raise ValueError('unexpected or missing allocated object sections: ' + repr(actual_sections ^ expected_sections))
        for name, address, size, section_name in CASES:
            original = object_elf.get_section_by_name(section_name)
            linked = linked_elf.get_section_by_name('.runtime_bss_' + name)
            symbol = symbols.get(name)
            if original is None or linked is None or symbol is None:
                raise ValueError('missing BSS section or symbol: ' + name)
            candidate = linked.data()
            exact = (original['sh_type'] == linked['sh_type'] == 'SHT_NOBITS'
                     and original['sh_size'] == linked['sh_size'] == size
                     and linked['sh_addr'] == symbol['st_value'] == address
                     and symbol['st_size'] == size and symbol['st_info']['type'] == 'STT_OBJECT'
                     and original['sh_flags'] & 3 == 3 and linked['sh_flags'] & 3 == 3
                     and address % original['sh_addralign'] == 0
                     and candidate == bytes(size))
            rows.append(dict(name=name, address=address, size=size, expected_size=size,
                             actual_size=linked['sh_size'], section=section_name,
                             output_section=linked.name, kind='zero_initialized_data',
                             origin='typed_nobits_object', alignment=original['sh_addralign'],
                             exact=exact, matching_bytes=size if exact else 0,
                             expected_sha256=sha(bytes(size)), actual_sha256=sha(candidate)))
            print(f'{name:30s} {address:#010x} {size:5d} bytes '
                  + ('EXACT NOBITS ABI' if exact else 'DIFF'))
    paths = {Path(__file__).resolve(), ROOT / 'tools/check-gd-toolchain.py',
             ROOT / 'tools/gd_function_gate.py', ROOT / 'tools/scatterload.py'}
    paths.update(Path(p).resolve() for p in shlex.split(
        dependencies.read_text().replace('\\\n', ' ').split(':', 1)[1]))
    report = dict(scope='typed zero-initialized object ABI/layout; not executable or initialized-flash coverage',
                  stock_md5=tc.STOCK_MD5, image_sha256=sha(stock),
                  zero_region=dict(address=ZI_START, size=ZI_SIZE, helper=zero_records[0][3]),
                  compiler=str(cc), compiler_sha256=sha(cc.read_bytes()), flags=flags,
                  commands=[compile_command, link_command],
                  source_sha256={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(paths)},
                  results=rows, aliases=ALIASES, unknown_intervals=unknown,
                  object_count=len(rows), exact_objects=sum(r['exact'] for r in rows),
                  typed_zero_bytes=sum(r['size'] for r in rows),
                  unclassified_zero_bytes=sum(g['size'] for g in unknown),
                  whole_zero_region_recovered=not unknown,
                  jump_buffer_evidence='Arm32 __int64 jmp_buf[20], local AC616/include/setjmp.h:57; '
                                       '160 bytes also fit observed 0x240089f8..0x24008a98 interval; '
                                       'not a claim of original compiler version')
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{report["exact_objects"]}/{len(rows)} typed objects verified, '
          f'{report["typed_zero_bytes"]}/{ZI_SIZE} zero-region bytes represented; '
          f'{report["unclassified_zero_bytes"]} bytes remain unclassified.')
    return int(not all(r['exact'] for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
