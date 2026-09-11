"""Shared full-section comparator for new mainBoardGD source modules.

Profiles supply actual C units, observed function extents and external symbol
addresses. Linked missing dependencies remain explicit and are not bodies.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'mcu/mainBoardGD/recovered'
COMPAT = ['-mllvm', '-arm-promote-constant', '-fno-unroll-loops', '-falign-loops=4',
          '-mllvm', '-enable-shrink-wrap=false', '-fno-builtin',
          '-mllvm', '-align-all-functions=1']


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, ROOT / 'tools' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main(label, cases, units, case_units, symbols, span_kind='function', extra_dependencies=(),
         semantic_references=()):
    if not set(semantic_references) <= {case[0] for case in cases}:
        raise ValueError('semantic reference names must be explicit checked cases')
    is_data = span_kind == 'constant_data'
    output_section = '.rodata' if is_data else '.text'
    input_prefix = '.rodata.' if is_data else '.text.'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc')
    parser.add_argument('--out', type=Path, default=ROOT / ('work/mainBoardGD-' + label))
    parser.add_argument('--cflag', action='append', default=[])
    args = parser.parse_args()
    tc, helper = load('check-gd-toolchain.py'), load('check-gd-motor.py')
    cc, out = tc.compiler_path(args.cc), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stock = tc.STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != tc.STOCK_MD5:
        raise ValueError('unexpected stock image')
    flags = [*tc.FLAGS, *COMPAT, *args.cflag]
    commands, dependencies = [], {Path(__file__).resolve(), Path(sys.argv[0]).resolve(),
                                  Path(tc.__file__).resolve(), Path(helper.__file__).resolve()}
    dependencies.update(Path(path).resolve() for path in extra_dependencies)
    for unit, (filename, defines) in units.items():
        depfile = out / (unit + '.d')
        command = [str(cc), *flags, *['-D' + define for define in defines],
                   '-MD', '-MF', str(depfile), '-MT', 'dependencies',
                   '-c', str(SOURCE / filename), '-o', str(out / (unit + '.o'))]
        subprocess.run(command, check=True)
        commands.append(command)
        dependencies.update(Path(name).resolve() for name in shlex.split(
            depfile.read_text().replace('\\\n', ' ').split(':', 1)[1]))
    rows = []
    for name, address, size in cases:
        script = out / (name + '.ld')
        script.write_text('\n'.join(f'{key} = {value:#x};' for key, value in symbols.items() if key != name)
                          + f'\nSECTIONS {{ {output_section} {address:#x} : {{ *({input_prefix}{name}) }}\n'
                          + ' /DISCARD/ : { *(.text*) '
                          + ('*(.rodata*) ' if is_data else '')
                          + '*(.ARM.exidx*) *(.ARM.extab*) } }\n')
        elf = out / (name + '.elf')
        subprocess.run([str(cc), *tc.FLAGS[:4], '-nostdlib', '-Wl,--entry=' + name,
                        '-Wl,-T,' + str(script), str(out / (case_units[name] + '.o')),
                        '-o', str(elf)], check=True)
        actual_address, actual = helper.section(elf, output_section)
        if actual_address != address:
            raise ValueError('incorrect linked address for ' + name)
        with elf.open('rb') as stream:
            linked = ELFFile(stream)
            entries = linked.get_section_by_name('.symtab').get_symbol_by_name(name)
            if not entries or len(entries) != 1:
                raise ValueError('missing/ambiguous function symbol: ' + name)
            entry_address = entries[0]['st_value'] if is_data else entries[0]['st_value'] & ~1
            if is_data:
                section = linked.get_section_by_name(output_section)
                if (entries[0]['st_info']['type'] != 'STT_OBJECT'
                        or entries[0]['st_size'] != len(actual)
                        or section['sh_type'] != 'SHT_PROGBITS'
                        or section['sh_flags'] & 7 != 2):
                    raise ValueError('constant data must be an actual read-only non-executable object: ' + name)
        offset = address + 0x4418 if address < 0x08000000 else address - 0x08000000
        expected = stock[offset:offset + size]
        if len(expected) != size:
            raise ValueError('stock range out of bounds')
        row = dict(name=name, kind=span_kind, address=address, expected_size=size, actual_size=len(actual),
                   actual_symbol_address=entry_address, entry_exact=entry_address == address,
                   exact=actual == expected and entry_address == address,
                   matching_bytes=sum(a == b for a, b in zip(actual, expected)),
                   expected_sha256=hashlib.sha256(expected).hexdigest(),
                   actual_sha256=hashlib.sha256(actual).hexdigest())
        if name in semantic_references:
            row['evidence_role'] = 'semantic_reference'
        rows.append(row)
        print(f'{name:32} {row["matching_bytes"]}/{size} bytes, size={len(actual)} '
              + ('EXACT' if row['exact'] else 'DIFF')
              + (f' (symbol entry shifted to {entry_address:#x})' if entry_address != address else ''))
    report = dict(scope=('compiled typed read-only data, not executable coverage'
                        if is_data else
                        'isolated architectural assembly spans, not C-function recovery'
                        if span_kind == 'runtime_assembly' else
                        'isolated full-function code/pool gate, not a complete firmware link'),
                  compiler=str(cc), compiler_sha256=hashlib.sha256(cc.read_bytes()).hexdigest(),
                  flags=flags, commands=commands, stock_md5=tc.STOCK_MD5,
                  source_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(dependencies)},
                  results=rows)
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    exact = [row for row in rows if row['exact']]
    description = ('constant objects' if is_data else
                   'architectural assembly spans' if span_kind == 'runtime_assembly' else 'functions')
    print(f'{len(exact)}/{len(rows)} exact {description}; {sum(row["expected_size"] for row in exact)} exact-span bytes')
    return int(len(exact) != len(rows))
