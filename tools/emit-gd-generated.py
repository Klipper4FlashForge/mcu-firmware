#!/usr/bin/env python3
"""Emit and verify the reconstructed mainBoardGD generated C layer.

  python3 tools/emit-gd-generated.py
  python3 tools/emit-gd-generated.py --check --verify

The extractor validates the stock metadata afresh. --check compares checked-in
source to deterministic emission. --verify compiles the C using ARM GCC/clang and
checks every data section against stock after linking symbolic pointers to
their observed runtime addresses. The validation linker script places lookup
code at 0x10000000: it is NOT a firmware link script or a code-match claim.
--verify-lookups separately compares the isolated lookup-match.c functions at
stock addresses, including their complete compiler-generated literal pools.
--promote-constants exposes a candidate global clang configuration explicitly.
--verify-runners checks the three actual generated call sequences. --report
writes byte intervals and source/compiler provenance after all requested gates,
even if one or more gates fails.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'mcu/mainBoardGD/recovered/generated'
VERIFICATION_RESULTS = []


def record_result(name, kind, address, expected, actual, **extra):
    result = dict(name=name, kind=kind, address=address, size=len(expected),
                  actual_size=len(actual), exact=actual == expected,
                  matching_bytes=sum(a == b for a, b in zip(actual, expected)),
                  expected_sha256=hashlib.sha256(expected).hexdigest(),
                  actual_sha256=hashlib.sha256(actual).hexdigest(), **extra)
    VERIFICATION_RESULTS.append(result)
    return result['exact']

# Direct branches in the stock functions, not the differing retained .ctr order.
RUNNERS = [
    ('ctr_run_initfuncs', 0x27c8, 26, [
        ('alloc_init', 0x7a8), ('initial_pins_setup', 0x3878),
        ('timer_cnt_init', 0x4ec8), ('mclib_init', 0x3d00), ('serial_init', 0x45a0)]),
    ('ctr_run_shutdownfuncs', 0x27e8, 38, [
        ('sendf_shutdown', 0x4518), ('move_reset', 0x3ed8),
        ('digital_out_shutdown', 0x2988), ('stepper_shutdown', 0x48b0),
        ('trsync_shutdown', 0x59d0), ('analog_in_shutdown', 0x868),
        ('clear_active_irq', 0xb10), ('timer_reset', 0x5590)]),
    ('ctr_run_taskfuncs', 0x2810, 50, [
        ('irq_poll', 0x3890), ('trsync_task', 0x5a40),
        ('irq_poll', 0x3890), ('analog_in_task', 0x8d0),
        ('irq_poll', 0x3890), ('buttons_task', 0xa58),
        ('irq_poll', 0x3890), ('timer_task', 0x5868),
        ('irq_poll', 0x3890), ('console_task', 0x20d8), ('irq_poll', 0x3890)]),
]


def extractor():
    spec = importlib.util.spec_from_file_location('gd_extract',
                        ROOT / 'tools/extract-gd-generated.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quote(text):
    return json.dumps(text, ensure_ascii=True)


def emit(metadata, itcm):
    sections = {}
    declarations, definitions = [], []

    def section(address, content):
        name = '.gd_generated_%08x' % address
        previous = sections.get(address)
        if previous is not None and previous != content:
            raise ValueError('conflicting section at %#x' % address)
        if itcm[address:address + len(content)] != content:
            raise ValueError('emitted data differs from stock at %#x' % address)
        sections[address] = content
        return 'GD_DATA("%s")' % name

    commands = metadata['command_index']['entries'][1:]
    encoders = metadata['encoders']
    parameters = {}
    for entry in commands + encoders:
        if entry['num_params']:
            address = entry['param_types_address']
            content = bytes(p['type_code'] for p in entry['parameters'])
            if address in parameters and parameters[address] != content:
                raise ValueError('inconsistent parameter array')
            parameters[address] = content
    for address, content in sorted(parameters.items()):
        values = ', '.join('PT_' + extractor_module.PT[n] for n in content)
        definitions.append('static const uint8_t command_parameters_%08x[] %s = { %s };'
                           % (address, section(address, content), values))

    def parameter_pointer(entry):
        if entry['num_params'] == 0:
            return 'NULL'
        return 'command_parameters_%08x' % entry['param_types_address']

    for entry in sorted(encoders, key=lambda e: e['address']):
        definitions.append(
            '// 0x%08x: %s\n'
            'const struct command_encoder command_encoder_%d %s = {\n'
            '    .encoded_msgid = %d, .max_size = %d, .num_params = %d,\n'
            '    .param_types = %s,\n};' % (
                entry['address'], entry['format'], entry['encoded_msgid'],
                section(entry['address'], bytes.fromhex(entry['raw_hex'])),
                entry['encoded_msgid'], entry['max_size'], entry['num_params'],
                parameter_pointer(entry)))

    blob = bytes.fromhex(metadata['identify']['compressed_hex'])
    rows = ['    ' + ', '.join('0x%02x' % b for b in blob[i:i + 12]) + ','
            for i in range(0, len(blob), 12)]
    definitions.append('const uint8_t command_identify_data[] %s = {\n%s\n};'
                       % (section(metadata['identify']['address'], blob), '\n'.join(rows)))
    size_address = metadata['identify']['size_address']
    definitions.append('const uint32_t command_identify_size %s = sizeof(command_identify_data);'
                       % section(size_address, len(blob).to_bytes(4, 'little')))

    index = metadata['command_index']
    rows = ['    { 0 }, // Reserved message id 0']
    for entry in commands:
        declarations.append('extern void %s(uint32_t *args);' % entry['handler_name'])
        rows.append('    { // %s\n'
                    '        .encoded_msgid = %d, .num_args = %d, .flags = %d,\n'
                    '        .num_params = %d, .param_types = %s, .func = %s,\n'
                    '    },' % (entry['format'], entry['encoded_msgid'], entry['num_args'],
                    entry['flags'], entry['num_params'], parameter_pointer(entry),
                    entry['handler_name']))
    index_raw = b''.join(bytes.fromhex(e['raw_hex']) for e in index['entries'])
    definitions.append('const struct command_parser command_index[] %s = {\n%s\n};'
                       % (section(index['address'], index_raw), '\n'.join(rows)))
    definitions.append('const uint16_t command_index_size %s =\n'
                       '    sizeof(command_index) / sizeof(command_index[0]);'
                       % section(index['size_address'], index['count'].to_bytes(2, 'little')))

    strings = {}
    for entry in encoders:
        strings[entry['format_address']] = entry['format']
    for entry in metadata['static_strings']:
        strings[entry['string_address']] = entry['text']
    for address, text in sorted(strings.items()):
        definition = ('const char generated_string_%08x[] %s = %s;'
                      % (address, section(address, text.encode() + b'\0'), quote(text)))
        if address < 0x3000:
            # The real firmware gets these from the lookup's compiler-generated
            # literal pools. Materialize them only for the compiler-independent
            # typed-data gate, where lookup machine code is deliberately absent.
            definition = '#ifdef GD_VERIFY_DATA_ONLY\n' + definition + '\n#endif'
        definitions.append(definition)

    header = '''/* Reconstructed generated-layer ABI. ARM32 sizes are verified at compile time.
 * Parameter enum and structures follow klipper/src/command.h. */
#ifndef MAINBOARDGD_GENERATED_H
#define MAINBOARDGD_GENERATED_H
#include <stddef.h>
#include <stdint.h>

enum {
    PT_uint32, PT_int32, PT_uint16, PT_int16, PT_byte,
    PT_string, PT_progmem_buffer, PT_buffer,
};
struct command_encoder {
    uint16_t encoded_msgid;
    uint8_t max_size, num_params;
    const uint8_t *param_types;
};
struct command_parser {
    uint16_t encoded_msgid;
    uint8_t num_args, flags, num_params;
    const uint8_t *param_types;
    void (*func)(uint32_t *args);
};
_Static_assert(sizeof(void *) == 4, "ARM32 pointers required");
_Static_assert(sizeof(struct command_encoder) == 8, "encoder ABI");
_Static_assert(offsetof(struct command_encoder, param_types) == 4, "encoder pointer ABI");
_Static_assert(sizeof(struct command_parser) == 16, "parser ABI");
_Static_assert(offsetof(struct command_parser, param_types) == 8, "parser pointer ABI");
_Static_assert(offsetof(struct command_parser, func) == 12, "handler pointer ABI");

extern const struct command_parser command_index[];
extern const uint16_t command_index_size;
extern const uint8_t command_identify_data[];
extern const uint32_t command_identify_size;
const struct command_encoder *ctr_lookup_encoder(const char *str);
uint8_t ctr_lookup_static_string(const char *str);
void ctr_run_initfuncs(void);
void ctr_run_shutdownfuncs(void);
void ctr_run_taskfuncs(void);
#endif
'''
    source = ('/* Generated by tools/emit-gd-generated.py from validated stock metadata.\n'
              ' * Explicit sections retain observed data addresses; no code bytes are embedded.\n'
              ' * Stock SHA256: %s\n */\n'
              '#include "generated.h"\n'
              '#define GD_DATA(name) __attribute__((section(name), used, aligned(1)))\n\n'
              % metadata['image']['sha256'])
    source += '\n'.join(sorted(set(declarations))) + '\n\n' + '\n\n'.join(definitions) + '\n'
    linker = ['/* DATA VALIDATION ONLY. Not a bootable firmware layout.',
              ' * Handler symbols resolve to measured stock Thumb addresses.',
              ' * Lookup code is placed away from stock; code equality is not tested. */',
              'SECTIONS', '{']
    last_end = 0
    for address, content in sorted(sections.items()):
        if address < last_end:
            raise ValueError('overlapping emitted sections')
        last_end = address + len(content)
        name = '.gd_generated_%08x' % address
        linker.append('    %s 0x%08x : { KEEP(*(%s)) }' % (name, address, name))
    linker += ['    .text 0x10000000 : { *(.text*) }',
               '    .ARM.exidx : { *(.ARM.exidx*) }',
               '    /DISCARD/ : { *(.comment) *(.note*) }', '}',
               'PROVIDE(strcmp = 0x08000459);']
    linker += ['PROVIDE(%s = 0x%08x);' % (e['handler_name'], e['handler_pointer'])
               for e in commands]
    manifest = dict(image_sha256=metadata['image']['sha256'],
                    purpose='Generated data only; lookup code is not byte-matched',
                    sections=[dict(name='.gd_generated_%08x' % a, address=a,
                                   size=len(b), raw_hex=b.hex())
                              for a, b in sorted(sections.items())])
    readme = '''# Reconstructed mainBoardGD generated layer

`generated.c` contains typed parser and response encoder records, parameter
arrays, shared strings, and the original compressed identify dictionary.
`lookup-match.c` contains the two C string lookup functions. These are separate
translation units of the same reconstructed layer, with no duplicate function
bodies. All values and lookup ordering are extracted from stock. The
shipped omission of `param_value` is preserved; unknown encoder strings return
NULL, and unknown static strings return 255.

`runners.c` supplies the three generated call-list functions from the actual
stock branch sequence. With the retained global configuration they reproduce
114/114 code bytes: init 26 bytes at 0x27c8, shutdown 38 bytes at 0x27e8, and
task 50 bytes at 0x2810. No runner has a literal pool. Following alignment gaps
(6, 2 and 6 bytes respectively) are not included in their function gates.

The source .ctr and generated calls disagree here too: watchdog_init and
watchdog_reset are declared but are absent from the shipped runners. The init
runner calls alloc_init, initial_pins_setup, timer_cnt_init, mclib_init (the
Klipper wrapper at 0x3d00), then serial_init. The task runner polls before and
after trsync_task, analog_in_task, buttons_task, timer_task, and console_task.
The shutdown runner's order is sendf_shutdown, move_reset, digital_out_shutdown,
stepper_shutdown, trsync_shutdown, analog_in_shutdown, clear_active_irq, timer_reset.
These sequences are validated against the actual Thumb branches on every emission.

Regenerate from the repository root:

```sh
python3 tools/emit-gd-generated.py
python3 tools/emit-gd-generated.py --check --verify
```

The second command compiles the C for ARM32 with the available GCC toolchain,
links its data at measured addresses, and compares every emitted data byte to
stock. The manifest records every checked range. Handler pointers resolve to
their stock addresses solely for this check; their bodies are separate work.

`verify-data.ld` is a data validation harness, not the firmware linker script.
For this check only, GD_VERIFY_DATA_ONLY materializes the eleven strings that
the real lookup compilation places in code-adjacent literal pools. The macro
is absent from the actual combined build. The stock compiler remains unpinned.
No executable machine-code arrays or binary includes are used.

`lookup-match.c` also supports an isolated executable lookup gate. Its local
string literals are expressed naturally; shared strings and
encoder records are external symbols resolved to their observed addresses by
`verify-lookups.ld`. The stock strcmp call goes through the ITCM veneer at
0x5b8a. `--verify-combined` builds both actual C translation units and links
their shared string and encoder symbols together using `verify-combined.ld`.
Only external handler bodies and the strcmp veneer remain address-only inputs.

ATfE 22.1.0 can run the same data check with `--compiler /path/to/clang`.
Its baseline `-O2 -mcpu=cortex-m7 -mfpu=fpv5-d16 -mfloat-abi=hard` emits
movw/movt for local strings. The explicit candidate GLOBAL setting
`--promote-constants` adds `-mllvm -arm-promote-constant`, reproducing stock's
ADR and literal-pool policy in both lookup functions. This is compiler
configuration evidence, not proof of the original compiler version.

```sh
python3 tools/emit-gd-generated.py --check --verify --verify-lookups \\
    --compiler work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang --promote-constants \\
    --cflag=-fno-unroll-loops --cflag=-falign-loops=4
```

Measured with ATfE 22.1.0: generated data remains 4,536/4,536 bytes exact in
102 sections. `ctr_lookup_encoder` is 640/640 bytes exact at 0x21a0: all
496 code bytes (160 instructions) and 144 literal-pool bytes. The static
lookup is still 862/932 bytes equal: 722/792 code bytes (218/284 instructions)
and all 140 pool bytes. Its return value uses r0 where stock uses r1. The
static pool ends at 0x27c4; following alignment before 0x27c8 is not claimed.
The combined lookup gate deliberately exits nonzero while this mismatch remains.

The register mismatch is explained by SelectionDAG scheduling: ATfE places the
final strcmp comparison before loading the default result (-1), permitting r0
to hold both. Stock loads the result in r1 before comparing r0, extending the
overlap and forcing r1 for the shared result in every return block.

Diagnostic `--cflag=-mllvm --cflag=-pre-RA-sched=list-burr` reproduces both
lookup functions exactly: 1,572/1,572 bytes including both literal pools and
444/444 instructions. With this diagnostic, `--verify-combined` verifies
5,956/5,956 unique bytes across the integrated data, lookup code and runners. Local
literal bytes are counted only once. All four original probes remain exact.
However, cross-module validation rejects adopting this scheduler globally:
SystemInit falls from 543/548 to 517/548 matching bytes, and the motor subset
falls from 10/13 exact functions (500 bytes) to 6/13 (282 bytes). No per-function
scheduler override has been added. This is diagnostic evidence, not a globally
valid recovery result. The normal global configuration still has the 70-byte
static-lookup difference.

Other global scheduler diagnostics: list-hybrid/list-ilp also match both lookups
but regress the original set_hold_current probe; fast/linearize grow the encoder
four bytes. Disabling machine scheduling, source/top-down/bottom-up scheduling,
register-pressure/live-use/vrcycle priorities, and two-address rescheduling does
not close the static mismatch. Disabling physical-register joining additionally
regresses the encoder. None of these alternatives is a default.

Three equivalent C spellings (shared exit/result variable, signed result with
else chain, signed-byte unknown return) produced the same static mismatch;
none was retained. All four original ATfE probes (timer_is_before,
timer_read_time, set_hold_current, set_run_current) remained exact, 126/126
bytes, when rebuilt with this same candidate global constant-promotion setting.

The canonical machine-readable verification report is generated with:

```sh
python3 tools/emit-gd-generated.py --check --verify --verify-lookups \\
    --verify-runners --verify-combined \\
    --compiler work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang --promote-constants \\
    --cflag=-fno-unroll-loops --cflag=-falign-loops=4 \\
    --report work/mainBoardGD-generated-verification.json
```

All requested gates execute even when a lookup or combined check fails. The
report records explicit failing intervals, separate exact literal-pool ranges,
source and expected/candidate byte hashes, and the complete compiler invocation.
Its overlapping data/pool intervals must be deduplicated when totaling progress.
Reports produced with rejected diagnostic compiler options must use a separate
filename and must not replace the canonical retained-configuration result.
'''
    lookup_source, lookup_linker = emit_lookup_probe(metadata)
    runner_source, runner_linker, runner_symbols = emit_runners(itcm)
    combined = ['/* Generated data + lookup integration at observed stock addresses.',
                ' * External handler bodies and strcmp veneer remain separate work. */',
                'SECTIONS {',
                '    .encoder 0x21a0 : { *(.text.ctr_lookup_encoder) }',
                '    .static_string 0x2420 : { *(.text.ctr_lookup_static_string) }']
    combined += ['    .%s 0x%x : { *(.text.%s) }' % (name, address, name)
                 for name, address, _, _ in RUNNERS]
    for address in sorted(sections):
        if address >= 0x3000:
            name = '.gd_generated_%08x' % address
            combined.append('    %s 0x%08x : { KEEP(*(%s)) }' % (name, address, name))
    combined += ['    .ARM.exidx : { *(.ARM.exidx*) }', '}',
                 'PROVIDE(strcmp = 0x00005b8b);']
    combined += ['PROVIDE(%s = 0x%08x);' % (e['handler_name'], e['handler_pointer'])
                 for e in commands]
    combined += runner_symbols
    return {'generated.h': header, 'generated.c': source,
            'verify-data.ld': '\n'.join(linker) + '\n',
            'data-manifest.json': json.dumps(manifest, indent=2, sort_keys=True) + '\n',
            'lookup-match.c': lookup_source, 'verify-lookups.ld': lookup_linker,
            'runners.c': runner_source, 'verify-runners.ld': runner_linker,
            'verify-combined.ld': '\n'.join(combined) + '\n',
            'README.md': readme}, manifest


def emit_lookup_probe(metadata):
    """Natural lookup source, isolated so candidate compiler settings are visible.

    Stock strings addressed with ADR are local literals; movw/movt strings and
    encoder objects are symbolic external dependencies at measured addresses.
    No code/data section rewriting or compiler-output patching is involved.
    """
    source = ['/* Isolated lookup reconstruction for compiler configuration checks.',
              ' * Local literals may be promoted by the compiler; shared strings and',
              ' * encoders are external dependencies located by verify-lookups.ld. */',
              '#include "generated.h"']
    linker = ['/* Isolated lookup comparison, not a bootable firmware link. */',
              'SECTIONS {',
              '  .encoder 0x21a0 : { *(.text.ctr_lookup_encoder) }',
              '  .static_string 0x2420 : { *(.text.ctr_lookup_static_string) }',
              '  .rodata 0x10000000 : { *(.rodata*) }',
              '  .ARM.exidx : { *(.ARM.exidx*) }',
              '}',
              '/* Stock BL calls an ITCM veneer, not the flash strcmp directly. */',
              'PROVIDE(strcmp = 0x00005b8b);']
    encoder_rows, static_rows = [], []
    for entry in metadata['encoders']:
        address, text = entry['format_address'], entry['format']
        symbol = 'command_encoder_%d' % entry['encoded_msgid']
        source.append('extern const struct command_encoder %s;' % symbol)
        linker.append('PROVIDE(%s = 0x%08x);' % (symbol, entry['address']))
        if address < 0x3000:
            expr = quote(text)
        else:
            expr = 'generated_string_%08x' % address
            source.append('extern const char %s[];' % expr)
            linker.append('PROVIDE(%s = 0x%08x);' % (expr, address))
        encoder_rows.append('    if (__builtin_strcmp(str, %s) == 0)\n'
                            '        return &%s;' % (expr, symbol))
    for entry in metadata['static_strings']:
        address, text = entry['string_address'], entry['text']
        if address < 0x3000:
            expr = quote(text)
        else:
            expr = 'generated_string_%08x' % address
            source.append('extern const char %s[];' % expr)
            linker.append('PROVIDE(%s = 0x%08x);' % (expr, address))
        static_rows.append('    if (__builtin_strcmp(str, %s) == 0)\n'
                           '        return %d;' % (expr, entry['result']))
    source += ['', 'const struct command_encoder *',
               'ctr_lookup_encoder(const char *str)', '{', *encoder_rows,
               '    return NULL;', '}', '', 'uint8_t',
               'ctr_lookup_static_string(const char *str)', '{', *static_rows,
               '    return 255;', '}']
    return '\n'.join(source) + '\n', '\n'.join(linker) + '\n'


def emit_runners(itcm):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    declarations, source, linker = {}, [], ['SECTIONS {']
    for name, address, size, calls in RUNNERS:
        insns = list(decoder.disasm(itcm[address:address + size], address))
        expected_calls = [target for _, target in calls]
        branches = [int(i.op_str.lstrip('#'), 0) for i in insns
                    if i.mnemonic in ('bl', 'b.w')]
        if (branches != expected_calls or insns[0].mnemonic != 'push'
                or insns[-1].mnemonic != 'b.w' or sum(i.size for i in insns) != size
                or len(insns) != len(calls) + 2):
            raise ValueError('stock runner no longer matches observed direct branch sequence: ' + name)
        source += ['/* Stock 0x%08x: %d code bytes; following alignment is separate. */'
                   % (address, size), 'void', name + '(void)', '{']
        for callee, target in calls:
            source.append('    %s(); // 0x%08x' % (callee, target))
            if callee in declarations and declarations[callee] != target:
                raise ValueError('inconsistent runner dependency address')
            declarations[callee] = target
        source += ['}', '']
        linker.append('    .%s 0x%x : { *(.text.%s) }' % (name, address, name))
    linker += ['    .ARM.exidx : { *(.ARM.exidx*) }', '}']
    symbols = ['PROVIDE(%s = 0x%08x);' % (name, target | 1)
               for name, target in sorted(declarations.items())]
    header = ['/* Recovered from actual branch order, not retained .ctr order.',
              ' * watchdog_init/watchdog_reset declarations have no corresponding',
              ' * call in the shipped generated runners.',
              ' * mclib_init here names the Klipper wrapper at 0x3d00. */',
              '#include "generated.h"', '']
    header += ['extern void %s(void);' % name for name in sorted(declarations)]
    return ('\n'.join(header + [''] + source) + '\n',
            '\n'.join(linker + symbols) + '\n', symbols)


def compile_command(compiler, promote, extra=()):
    clang = 'clang' in Path(compiler).name
    command = [compiler, '-std=c11', '-O2' if clang else '-Os',
               '-mcpu=cortex-m7', '-mthumb', '-ffunction-sections', '-fdata-sections',
               '-Wall', '-Wextra', '-Werror']
    if clang:
        command += ['--target=arm-none-eabi', '-mfpu=fpv5-d16', '-mfloat-abi=hard']
    if promote:
        if not clang:
            raise ValueError('--promote-constants requires clang')
        command += ['-mllvm', '-arm-promote-constant']
    return command + list(extra)


def verify(directory, manifest, prefix, compiler, promote, extra=()):
    with tempfile.TemporaryDirectory(prefix='mainboardgd-generated-') as temp:
        temp = Path(temp)
        subprocess.run(compile_command(compiler, promote, extra) +
                       ['-DGD_VERIFY_DATA_ONLY', '-c', str(directory / 'generated.c'),
                        '-o', str(temp / 'generated.o')],
                       check=True)
        subprocess.run([prefix + 'ld', '-T', str(directory / 'verify-data.ld'),
                        str(temp / 'generated.o'), '-o', str(temp / 'generated.elf')], check=True)
        total = 0
        for index, entry in enumerate(manifest['sections']):
            target = temp / ('section-%d.bin' % index)
            subprocess.run([prefix + 'objcopy', '--dump-section',
                            entry['name'] + '=' + str(target), str(temp / 'generated.elf')],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not record_result(entry['name'], 'generated_data', entry['address'],
                                 bytes.fromhex(entry['raw_hex']), target.read_bytes(),
                                 verification='typed_data'):
                raise ValueError('compiled section differs: ' + entry['name'])
            total += entry['size']
        print('ARM32 compiled data: %d/%d bytes exact across %d sections; lookup code not scored'
              % (total, total, len(manifest['sections'])))


def verify_lookups(directory, itcm, prefix, compiler, promote, extra=()):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    with tempfile.TemporaryDirectory(prefix='mainboardgd-lookups-') as temp:
        temp = Path(temp)
        subprocess.run(compile_command(compiler, promote, extra) +
                       ['-c', str(directory / 'lookup-match.c'), '-o', str(temp / 'lookup.o')],
                       check=True)
        subprocess.run([prefix + 'ld', '-T', str(directory / 'verify-lookups.ld'),
                        str(temp / 'lookup.o'), '-o', str(temp / 'lookup.elf')], check=True)
        exact = True
        for name, start, code_end, pool_end in [
                ('encoder', 0x21a0, 0x2390, 0x2420),
                ('static_string', 0x2420, 0x2738, 0x27c4)]:
            binary = temp / (name + '.bin')
            subprocess.run([prefix + 'objcopy', '--dump-section', '.' + name + '=' + str(binary),
                            str(temp / 'lookup.elf')], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            actual, expected = binary.read_bytes(), itcm[start:pool_end]
            code_size = code_end - start
            count = sum(a == b for a, b in zip(actual, expected))
            code_count = sum(a == b for a, b in zip(actual[:code_size], expected[:code_size]))
            pool_exact = actual[code_size:] == expected[code_size:]
            matched = actual == expected
            exact &= matched
            record_result('ctr_lookup_' + name, 'function_span_code_and_pool', start,
                          expected, actual, code_end=code_end, pool_end=pool_end,
                          verification='isolated_lookup')
            record_result('ctr_lookup_' + name + ' literal pool', 'literal_pool', code_end,
                          expected[code_size:], actual[code_size:], verification='isolated_lookup')
            print('%s: %s; bytes %d/%d, emitted size %d; code %d/%d; pool %s (%d bytes)'
                  % (name, 'EXACT' if matched else 'DIFF', count, len(expected), len(actual),
                     code_count, code_size, 'EXACT' if pool_exact else 'DIFF', len(expected)-code_size))
            actual_insns = [(i.mnemonic, i.op_str) for i in decoder.disasm(actual[:code_size], start)]
            stock_insns = [(i.mnemonic, i.op_str) for i in decoder.disasm(expected[:code_size], start)]
            print('  instructions %d/%d equal at original absolute addresses'
                  % (sum(a == b for a, b in zip(actual_insns, stock_insns)), len(stock_insns)))
        if not exact:
            raise ValueError('lookup code/pool gate not yet exact')


def verify_combined(directory, itcm, manifest, prefix, compiler, promote, extra=()):
    """Link the actual C translation units together; check every recovered byte."""
    with tempfile.TemporaryDirectory(prefix='mainboardgd-generated-combined-') as temp:
        temp = Path(temp)
        objects = []
        for name in ('generated', 'lookup-match', 'runners'):
            target = temp / (name + '.o')
            subprocess.run(compile_command(compiler, promote, extra) +
                           ['-c', str(directory / (name + '.c')), '-o', str(target)], check=True)
            objects.append(str(target))
        elf, binary = temp / 'combined.elf', temp / 'combined.bin'
        subprocess.run([prefix + 'ld', '-T', str(directory / 'verify-combined.ld'),
                        *objects, '-o', str(elf)], check=True)
        subprocess.run([prefix + 'objcopy', '-O', 'binary',
                        '--only-section=.encoder', '--only-section=.static_string',
                        '--only-section=.ctr_run_*',
                        '--only-section=.gd_generated_*', str(elf), str(binary)], check=True)
        data, base = binary.read_bytes(), 0x21a0
        checked = set()
        ranges = [(e['address'], bytes.fromhex(e['raw_hex']), e['name'])
                  for e in manifest['sections']]
        ranges += [(0x21a0, itcm[0x21a0:0x2420], 'encoder code + pool'),
                   (0x2420, itcm[0x2420:0x27c4], 'static-string code + pool')]
        ranges += [(address, itcm[address:address + size], name)
                   for name, address, size, _ in RUNNERS]
        failures = []
        for address, expected, name in ranges:
            actual = data[address - base:address - base + len(expected)]
            kind = 'generated_data' if name.startswith('.gd_generated_') else 'function_span_code_and_pool'
            code_end = {0x21a0: 0x2390, 0x2420: 0x2738}.get(address, address + len(expected))
            extra = {} if kind == 'generated_data' else dict(code_end=code_end, pool_end=address + len(expected))
            if not record_result(name, kind, address, expected, actual,
                                 verification='combined', **extra):
                failures.append(name)
            checked.update(range(address, address + len(expected)))
        for start, end in ((0x2390, 0x2420), (0x2738, 0x27c4)):
            record_result('combined literal pool at %#x' % start, 'literal_pool', start,
                          itcm[start:end], data[start-base:end-base], verification='combined')
        if failures:
            raise ValueError('combined generated layer differs: ' + ', '.join(failures))
        print('Combined typed data + both C lookups: %d/%d unique bytes EXACT '
              '(shared symbols linked together, handler/strcmp dependencies external)'
              % (len(checked), len(checked)))


def verify_runners(directory, itcm, prefix, compiler, promote, extra=()):
    with tempfile.TemporaryDirectory(prefix='mainboardgd-runners-') as temp:
        temp = Path(temp)
        obj, elf = temp / 'runners.o', temp / 'runners.elf'
        subprocess.run(compile_command(compiler, promote, extra) +
                       ['-c', str(directory / 'runners.c'), '-o', str(obj)], check=True)
        subprocess.run([prefix + 'ld', '-T', str(directory / 'verify-runners.ld'),
                        str(obj), '-o', str(elf)], check=True)
        all_exact = True
        for name, address, size, _ in RUNNERS:
            binary = temp / (name + '.bin')
            subprocess.run([prefix + 'objcopy', '--dump-section', '.' + name + '=' + str(binary),
                            str(elf)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            actual, expected = binary.read_bytes(), itcm[address:address + size]
            exact = actual == expected
            all_exact &= exact
            record_result(name, 'function_span_code_and_pool', address, expected, actual,
                          code_end=address + size, pool_end=address + size,
                          verification='isolated_runner')
            print('%s: %s %d/%d code bytes, emitted size %d; no literal pool'
                  % (name, 'EXACT' if exact else 'DIFF',
                     sum(a == b for a, b in zip(actual, expected)), size, len(actual)))
        if not all_exact:
            raise ValueError('generated runner gate not exact')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path,
                        default=ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin')
    parser.add_argument('--out-dir', type=Path, default=DEST)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--verify-lookups', action='store_true')
    parser.add_argument('--verify-combined', action='store_true')
    parser.add_argument('--verify-runners', action='store_true')
    parser.add_argument('--report', type=Path, help='write verification results/provenance JSON even on mismatches')
    parser.add_argument('--compiler', help='compiler path; defaults to tool-prefix + gcc')
    parser.add_argument('--promote-constants', action='store_true',
                        help='explicit candidate GLOBAL clang setting: -mllvm -arm-promote-constant')
    parser.add_argument('--cflag', action='append', default=[],
                        help='additional candidate GLOBAL compiler option')
    parser.add_argument('--tool-prefix', default=str(ROOT /
        'work/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-'))
    args = parser.parse_args()
    errors = []
    metadata, files = None, {}
    VERIFICATION_RESULTS.clear()
    try:
        metadata, itcm, _ = extractor_module.extract(args.image.read_bytes())
        files, manifest = emit(metadata, itcm)
        if not args.check:
            args.out_dir.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            path = args.out_dir / name
            if args.check:
                if not path.exists() or path.read_text() != text:
                    raise ValueError('generated source is stale: ' + str(path))
            else:
                path.write_text(text)
        print('%s %d generated source/validation files' %
              ('checked' if args.check else 'emitted', len(files)))
        common = (args.tool_prefix, args.compiler or args.tool_prefix + 'gcc',
                  args.promote_constants, args.cflag)
        gates = [
            (args.verify, 'typed_data', verify, (args.out_dir, manifest, *common)),
            (args.verify_lookups, 'lookups', verify_lookups, (args.out_dir, itcm, *common)),
            (args.verify_runners, 'runners', verify_runners, (args.out_dir, itcm, *common)),
            (args.verify_combined, 'combined', verify_combined,
             (args.out_dir, itcm, manifest, *common)),
        ]
        for enabled, name, function, params in gates:
            if enabled:
                try:
                    function(*params)
                except (ValueError, OSError, subprocess.CalledProcessError) as error:
                    errors.append('%s: %s' % (name, error))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        errors.append('generation: %s' % error)
    if args.report:
        sources = [args.out_dir / name for name in files if name.endswith(('.c', '.h', '.ld'))]
        sources += [Path(__file__).resolve(), ROOT / 'tools/extract-gd-generated.py']
        hashes = {str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT)
                  else str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sources if path.exists()}
        report = dict(schema_version=1, image_sha256=metadata['image']['sha256'] if metadata else None,
                      source_sha256=hashes, invocation=[sys.executable, *sys.argv],
                      compiler_command=compile_command(args.compiler or args.tool_prefix + 'gcc',
                                                       args.promote_constants, args.cflag),
                      results=VERIFICATION_RESULTS, errors=errors,
                      all_requested_gates_passed=bool(VERIFICATION_RESULTS) and not errors)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    if errors:
        parser.exit(1, '\n'.join(errors) + '\n')


extractor_module = extractor()
if __name__ == '__main__':
    main()
