#!/usr/bin/env python3
"""Link recovered mainBoardGD units together, auditing unrecovered dependencies.

This is a partial integration ELF, NOT flashable firmware. Every recovered
function has its observed execution address. Missing dependencies are named
absolute symbols, never dummy bodies or copied stock instructions. Generic
cross-region veneers are assembled from symbolic targets, replacing the role
of armlink's veneer generation; C instruction selection is never rewritten.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

from elftools.elf.elffile import ELFFile
from scatterload import decompress

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mcu/mainBoardGD/recovered"
COMPAT = ["-mllvm", "-arm-promote-constant", "-fno-unroll-loops", "-falign-loops=4",
          "-mllvm", "-enable-shrink-wrap=false", "-fno-builtin",
          "-mllvm", "-align-all-functions=1"]
PREFIX = str(ROOT / "work/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-")
ARMCLANG = ROOT / "work/atfe/ac6.20/bin/armclang"


def module(filename):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), ROOT / "tools" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def object_info(path):
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        sections = {s.name: dict(size=s["sh_size"], type=s["sh_type"], flags=s["sh_flags"],
                                 align=s["sh_addralign"])
                    for s in elf.iter_sections()}
        symbols = {s.name: dict(index=s["st_shndx"], value=s["st_value"],
                                type=s["st_info"]["type"])
                   for s in elf.get_section_by_name(".symtab").iter_symbols()
                   if s.name and s["st_info"]["bind"] != "STB_LOCAL"}
    return sections, symbols


def source_name(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc")
    parser.add_argument("--cflag", action="append", default=[],
                        help="diagnostic option applied globally to every C unit")
    parser.add_argument("--out", type=Path, default=ROOT / "work/mainBoardGD-partial")
    parser.add_argument("--linker", help="clang driver used for the link step when --cc is an "
                                          "armclang, whose driver cannot take a GNU ld script")
    parser.add_argument("--no-compat", action="store_true",
                        help="drop the measured ATfE compatibility flags (compiler sweeps only)")
    parser.add_argument("--diagnostic-overflow", action="store_true", default=True,
                        help="(default) link a C body that overruns its stock slot in a scratch "
                             "region instead of failing; callers still bind to the stock address "
                             "and the report marks the row overflow")
    parser.add_argument("--strict", action="store_false", dest="diagnostic_overflow",
                        help="fail on an overrunning body instead")
    args = parser.parse_args()
    tc, motor, core, gpio = [module("check-gd-" + name + ".py")
                            for name in ("toolchain", "motor", "core", "gpio")]
    generated = module("emit-gd-generated.py")
    layout = module("extract-gd-layout.py").extract(tc.STOCK.read_bytes())
    # The stock compiler is Arm Compiler for Embedded at uVision's default -O1
    # (notes/compiler-version-sweep.md); the ATfE path with its compatibility
    # flags remains available as the pre-2026-09-11 reference.
    cc = tc.compiler_path(args.cc) if args.cc or not ARMCLANG.exists() else ARMCLANG
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    armclang = cc.name.startswith("armclang")
    flags = [*(["-O1" if f == "-O2" else f for f in tc.FLAGS] if armclang else tc.FLAGS),
             *([] if args.no_compat or armclang else COMPAT), *args.cflag,
             "-I" + str(ROOT / "klipper/lib/cmsis-core")]
    linker = Path(args.linker).resolve() if args.linker else cc
    if armclang:
        # Arm Compiler's driver spells the same bare-metal target with a vendor
        # field, cannot take a GNU ld script (so the ATfE driver links), and
        # wants CMSIS 5.7.0's cmsis_armclang.h, which Klipper's import omits.
        flags = ["--target=arm-arm-none-eabi" if f == "--target=arm-none-eabi" else f for f in flags]
        if not args.linker:
            linker = ROOT / "work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang"
        flags.append("-I" + str(ROOT / "work/cmsis-armclang"))
    stock = tc.STOCK.read_bytes()
    units = {"motor_" + unit: ("mclib_commands.c", [define] if define else [])
             for unit, define in motor.UNITS.items()}
    units.update({"gpio_vendor": ("gpio.c", ["GD_GPIO_VENDOR"]),
             "gpio_clock": ("gpio.c", ["GD_GPIO_CLOCK"]),
             "gpio_board": ("gpio.c", []),
             "system_init": ("system_init.c", []),
             "generated": ("generated/generated.c", []),
             "lookups": ("generated/lookup-match.c", []),
             "runners": ("generated/runners.c", [])})
    functions = []
    for name, address, size, flash in motor.CASES:
        functions.append(dict(name=name, address=address, size=size,
                              unit="motor_" + motor.CASE_UNITS[name]))
    for name, address, size, unit in core.CASES:
        units[unit] = (unit + ".c", [])
        functions.append(dict(name=name, address=address, size=size, unit=unit))
    for name, address, size, group in gpio.CASES:
        functions.append(dict(name=name, address=address, size=size, unit="gpio_" + group))
    for name, address, size, unit in [
            ("SystemInit", 0x08000620, 548, "system_init"),
            ("ctr_lookup_encoder", 0x21a0, 640, "lookups"),
            ("ctr_lookup_static_string", 0x2420, 932, "lookups")]:
        functions.append(dict(name=name, address=address, size=size, unit=unit))
    for name, address, size, _ in generated.RUNNERS:
        functions.append(dict(name=name, address=address, size=size, unit="runners"))

    # Shared stock dependency names from existing validated address profiles.
    addresses = {}
    serial = module("check-gd-serial.py")
    base = module("check-gd-base.py")
    protocol = module("check-gd-protocol.py")
    runtime = module("check-gd-runtime.py")
    scatter_handlers = module('check-gd-scatter-handlers.py')
    bss = module("check-gd-bss.py")
    stepper = module('check-gd-stepper.py')
    mpu = module('check-gd-mpu.py')
    board = module('check-gd-board.py')
    trsync = module('check-gd-trsync.py')
    gpio_output = module('check-gd-gpio-output.py')
    memory = module('check-gd-memory.py')
    irqs = module('check-gd-irqs.py')
    adc_irqs = module('check-gd-adc-irqs.py')
    dma_irqs = module('check-gd-dma-irqs.py')
    endstop = module('check-gd-endstop.py')
    math = module('check-gd-math.py')
    hardware = module('check-gd-hardware.py')
    scatter_runtime = module('check-gd-scatter-runtime.py')
    adc_vendor = module('check-gd-adc-vendor.py')
    digital_out = module('check-gd-digital-out.py')
    angles = module('check-gd-angles.py')
    dma_vendor = module('check-gd-dma-vendor.py')
    interrupt_control = module('check-gd-interrupt-control.py')
    analog_in = module('check-gd-analog-in.py')
    buttons = module('check-gd-buttons.py')
    trig = module('check-gd-trig.py')
    timer_vendor = module('check-gd-timer-vendor.py')
    config_finalize = module('check-gd-config-finalize.py')
    pwm_vendor = module('check-gd-pwm-vendor.py')
    debug_scope = module('check-gd-debug-scope.py')
    new_profiles = (dma_vendor, interrupt_control, analog_in, buttons, trig,
                    timer_vendor, config_finalize, pwm_vendor, debug_scope)
    protocol_data = module('check-gd-protocol-data.py')
    sdk = module('check-gd-sdk.py')
    units.update(sdk.UNITS)
    for name, address, size, unit in sdk.CASES:
        functions.append(dict(name=name, address=address, size=size, unit=unit))
    constant_profiles = [(sdk.DATA_UNITS, sdk.DATA_CASES, sdk.DATA_CASE_UNITS),
                         (protocol_data.UNITS, protocol_data.CASES, protocol_data.CASE_UNITS),
                         (angles.DATA_UNITS, angles.DATA_CASES, angles.DATA_CASE_UNITS),
                         (trig.DATA_UNITS, trig.DATA_CASES, trig.DATA_CASE_UNITS),
                         (timer_vendor.DATA_UNITS, timer_vendor.DATA_CASES, timer_vendor.DATA_CASE_UNITS),
                         (debug_scope.DATA_UNITS, debug_scope.DATA_CASES, debug_scope.DATA_CASE_UNITS)]
    constants = []
    for data_units, data_cases, data_case_units in constant_profiles:
        units.update(data_units)
        for name, address, size, *section in data_cases:
            constants.append(dict(name=name, address=address, size=size, unit=data_case_units[name],
                                  **(dict(section=section[0]) if section else {})))
    # A flash caller and an ITCM caller can name the same function while
    # targeting different observed bridges. Keep call-site bindings per unit;
    # only accept global name differences when the layout proves equivalence.
    bridge_targets = {row['address']: row['thumb_pointer'] for row in layout['veneers']}
    def resolved_target(address):
        return bridge_targets.get(address & ~1, address)

    unit_addresses = {}
    for profile in (serial, base, protocol, runtime, stepper, mpu, board,
                    trsync, gpio_output, memory, irqs, adc_irqs, dma_irqs,
                    endstop, math, hardware, scatter_runtime, adc_vendor, digital_out, angles,
                    *new_profiles):
        for unit in profile.UNITS:
            unit_addresses[unit] = profile.SYMBOLS
    for unit, references in sdk.UNIT_REFERENCES.items():
        unit_addresses[unit] = references
    standalone_exclusions = []
    for profile, names in ((memory, {c[0] for c in memory.CASES if c[0] not in {'strcmp', 'memset'}}),
                           (scatter_runtime, {'gd_runtime_decompress'})):
        for name, address, size in profile.CASES:
            if name in names:
                standalone_exclusions.append(dict(name=name, address=address, stock_size=size,
                    unit=profile.CASE_UNITS[name],
                    reason='candidate exceeds fixed slot with required alignment; see isolated gate'))
    semantic_reference_exclusions = [dict(name=name, address=address, stock_size=size,
        unit=scatter_runtime.CASE_UNITS[name],
        reason='C semantic reference only; original handlers.s implementation is integrated as runtime assembly')
        for name, address, size in scatter_runtime.CASES
        if name in scatter_runtime.SEMANTIC_REFERENCES]
    excluded_names = {row['name'] for row in standalone_exclusions + semantic_reference_exclusions}
    excluded_units = {row['unit'] for row in standalone_exclusions + semantic_reference_exclusions}
    for profile in (stepper, mpu, board, trsync, gpio_output, memory,
                    irqs, adc_irqs, dma_irqs, endstop, math, hardware,
                    scatter_runtime, adc_vendor, digital_out, angles, *new_profiles):
        units.update({name: unit for name, unit in profile.UNITS.items()
                      if name not in excluded_units})
        for name, address, size in profile.CASES:
            if name not in excluded_names:
                functions.append(dict(name=name, address=address, size=size,
                                      unit=profile.CASE_UNITS[name]))
    units.update(runtime.UNITS)
    units['runtime_state'] = ('runtime_state.c', [])
    for name, address, size in runtime.CASES:
        functions.append(dict(name=name, address=address, size=size,
                              unit=runtime.CASE_UNITS[name], source_kind='runtime_assembly'))
    units.update(scatter_handlers.UNITS)
    for name, address, size in scatter_handlers.CASES:
        functions.append(dict(name=name, address=address, size=size,
                              unit=scatter_handlers.CASE_UNITS[name], source_kind='runtime_assembly'))
    units.update(protocol.UNITS)
    for name, address, size in protocol.CASES:
        functions.append(dict(name=name, address=address, size=size,
                              unit=protocol.CASE_UNITS[name]))
    units.update(base.UNITS)
    for name, address, size in base.CASES:
        functions.append(dict(name=name, address=address, size=size, unit=base.CASE_UNITS[name]))
    units.update(serial.UNITS)
    for name, address, size in serial.CASES:
        unit = serial.CASE_UNITS[name]
        functions.append(dict(name=name, address=address, size=size, unit=unit))
    state = module("check-gd-state.py")
    ctr = module("emit-gd-ctr.py")
    units["state"] = ("state.c", [])
    units["ctr"] = ("compile_time_requests.c", [])
    for profile in (motor.SYMBOLS, core.SYMBOLS, gpio.SYMBOLS, serial.SYMBOLS,
                    state.SYMBOLS, base.SYMBOLS, protocol.SYMBOLS, runtime.SYMBOLS, bss.SYMBOLS,
                    stepper.SYMBOLS, mpu.SYMBOLS, board.SYMBOLS, trsync.SYMBOLS,
                    gpio_output.SYMBOLS, memory.SYMBOLS, irqs.SYMBOLS,
                    adc_irqs.SYMBOLS, dma_irqs.SYMBOLS, endstop.SYMBOLS,
                    math.SYMBOLS, hardware.SYMBOLS, scatter_runtime.SYMBOLS,
                    adc_vendor.SYMBOLS, digital_out.SYMBOLS, angles.SYMBOLS, sdk.SYMBOLS,
                    *(profile.SYMBOLS for profile in new_profiles)):
        for name, address in profile.items():
            if name in addresses and addresses[name] != address:
                if resolved_target(addresses[name]) != resolved_target(address):
                    raise ValueError("conflicting dependency address: " + name)
            else:
                addresses[name] = address
    provides = (SOURCE / "generated/verify-combined.ld").read_text()
    for name, value in re.findall(r"PROVIDE\((\w+) = (0x[0-9a-f]+)\);", provides):
        address = int(value, 16)
        if name in addresses and addresses[name] != address:
            raise ValueError("conflicting generated dependency address: " + name)
        addresses[name] = address

    # Vector entries are typed symbolic pointers. Unknown handlers remain
    # explicit missing dependencies; known ones bind to actual C definitions.
    function_targets = {row["address"]: row["name"] for row in functions}
    function_targets.update(runtime.EXTRA_FUNCTIONS)
    vector_targets = {}
    for vector in layout["vectors"]:
        if vector["pointer"]:
            target = vector["target"]
            name = function_targets.get(target, "gd_missing_%08x" % target)
            vector_targets[target] = name
            if name.startswith("gd_missing_"):
                addresses[name] = vector["pointer"]
    vectors = ["/* Symbolic mainBoardGD vector table; no instruction data. */",
               "struct gd_vector_table { void *initial_sp; void (*handler[232])(void); };"]
    vectors += ["extern void " + name + "(void);" for name in sorted(set(vector_targets.values()))]
    vectors += ['__attribute__((section(".gd_vectors"), used))',
                "const struct gd_vector_table gd_vectors = {",
                "    (void *)0x%08x, {" % layout["initial_sp"]]
    for vector in layout["vectors"]:
        vectors.append("    " + (vector_targets[vector["target"]] if vector["pointer"] else "0")
                       + ", /* slot %d */" % vector["slot"])
    vectors += ["} };", "_Static_assert(sizeof(gd_vectors) == 932, \"vector table extent\");"]
    vector_source = out / "vectors.c"
    vector_source.write_text("\n".join(vectors) + "\n")
    units["vectors"] = (str(vector_source), [])

    # A unit whose every span has moved to a library file is not compiled:
    # its definitions would duplicate the library's.
    placing = {row["unit"] for row in [*functions, *constants]}
    placing.update({"vectors", "state", "clock_tables", "ctr", "generated", "lookups",
                    "runtime_state", "runners"})
    placing.update(unit for unit in units if unit in {row["unit"] for row in functions})
    units = {unit: value for unit, value in units.items() if unit in placing}
    library_flags = ["-w", "-I" + str(SOURCE / "lib/gd32h7xx/Include")]
    flags += ["-I" + str(SOURCE / "lib/gd32h7xx/Include"), "-DGD32H7XX"]
    objects, info, commands, dependencies = {}, {}, [], set()
    for unit, (filename, defines) in sorted(units.items()):
        obj = out / (unit + ".o")
        depfile = out / (unit + '.d')
        command = [str(cc), *flags, *(library_flags if unit in sdk.LIBRARY_UNITS else []),
                   *["-D" + define for define in defines],
                   '-MD', '-MF', str(depfile), '-MT', 'dependencies',
                   "-c", str(SOURCE / filename), "-o", str(obj)]
        subprocess.run(command, check=True)
        objects[unit], info[unit] = obj, object_info(obj)
        commands.append(command)
        dependencies.update(Path(name).resolve() for name in shlex.split(
            depfile.read_text().replace('\\\n', ' ').split(':', 1)[1]))
    definitions = {}
    for unit, (_, symbols) in info.items():
        for name, entry in symbols.items():
            if entry["index"] == "SHN_UNDEF":
                continue
            if name in definitions:
                raise ValueError("duplicate actual definition: " + name)
            definitions[name] = unit

    # A linker-level bridge always has the same three instructions. Absolute
    # addresses are supplied through symbol relocations, not opcode literals.
    bridges = {row["address"]: row for row in layout["veneers"]}
    targets = {row["address"]: row["name"] for row in functions}
    targets.update(runtime.EXTRA_FUNCTIONS)
    assembly = [".syntax unified", ".thumb"]
    for address, bridge in sorted(bridges.items()):
        name = "gd_bridge_%08x" % address
        target = targets.get(bridge["target"], "gd_missing_%08x" % bridge["target"])
        if target.startswith("gd_missing_"):
            addresses[target] = bridge["thumb_pointer"]
        bridge["symbol"], bridge["target_symbol"] = name, target
        assembly += [f'.section .text.{name},"ax",%progbits', ".balign 2",
                     ".global " + name, ".type " + name + ",%function", ".thumb_func",
                     name + ":", "movw ip, #:lower16:" + target,
                     "movt ip, #:upper16:" + target, "bx ip", ".size " + name + ", .-" + name]
    asm = out / "linker-bridges.S"
    asm.write_text("\n".join(assembly) + "\n")
    bridge_obj = out / "linker-bridges.o"
    subprocess.run([str(cc), *tc.FLAGS[:4], "-c", str(asm), "-o", str(bridge_obj)], check=True)

    # Redirect undefined references whose observed target is a veneer, or a
    # separately proven direct call to an explicitly unrecovered bridge target.
    # Real function definitions and ordinary data/function pointers keep their
    # original names. This is a recorded linker relocation-routing operation.
    rewrites = []
    for unit, (_, symbols) in info.items():
        options = []
        for name, entry in symbols.items():
            reference_address = unit_addresses.get(unit, {}).get(name, addresses.get(name, 0))
            if entry["index"] == "SHN_UNDEF" and (reference_address & ~1) in bridges:
                bridge = bridges[reference_address & ~1]
                options += ["--redefine-sym", name + "=" + bridge["symbol"]]
                rewrites.append(dict(unit=unit, reference=name, routed_to=bridge["symbol"]))
            elif (entry["index"] == "SHN_UNDEF" and name not in definitions
                  and reference_address != addresses.get(name, 0)):
                # A direct call must not silently inherit another caller's
                # veneer-valued absolute binding when its body is still absent.
                # PWM channel setup calls the oversized OC-shadow body directly,
                # while hardware initialization uses its flash bridge. The
                # extracted bridge must prove both addresses refer to one body.
                global_address = addresses.get(name, 0)
                if ((global_address & ~1) not in bridges
                        or resolved_target(global_address) != reference_address):
                    raise ValueError('unresolved direct-call binding differs from global profile: '
                                     + unit + ':' + name)
                target = bridges[global_address & ~1]['target_symbol']
                if addresses.get(target) != reference_address:
                    raise ValueError('direct-call bridge target lacks explicit missing binding: '
                                     + unit + ':' + name)
                options += ['--redefine-sym', name + '=' + target]
                rewrites.append(dict(unit=unit, reference=name, routed_to=target,
                                     kind='explicit_unrecovered_direct_call',
                                     address=reference_address))
        if options:
            routed = out / (unit + ".routed.o")
            subprocess.run([PREFIX + "objcopy", *options, str(objects[unit]), str(routed)], check=True)
            objects[unit] = routed

    placed = {("vectors", ".gd_vectors")}
    rows = [dict(name="gd_vectors", unit="vectors", kind="vectors", input_section=".gd_vectors",
                 output_section=".vectors", address=0x08000000, size=932, actual_size=932)]
    for function in functions:
        section = ".text." + function["name"]
        unit = function["unit"]
        if section not in info[unit][0]:
            raise ValueError("missing compiled function section: " + section)
        function["actual_size"] = info[unit][0][section]["size"]
        function["input_align"] = info[unit][0][section]["align"]
        output = ".fn." + function["name"]
        rows.append(dict(**function, input_section=section, output_section=output,
                         kind=function.get('source_kind', 'function')))
        placed.add((unit, section))
    for constant in constants:
        unit, name = constant['unit'], constant['name']
        section = constant.pop('section', None)
        constant['generated'] = section is not None  # a compiler table, not a named object
        section = section or '.rodata.' + name
        if section not in info[unit][0]:
            raise ValueError('missing compiled constant object: ' + name)
        rows.append(dict(**constant, kind='constant_data', input_section=section,
                         output_section='.constant.' + name,
                         actual_size=info[unit][0][section]['size']))
        placed.add((unit, section))
    manifest = json.loads((SOURCE / "generated/data-manifest.json").read_text())
    bss.holes()  # Validate bounds and non-overlap independently of compiled sizes.
    for name, address, size, section in bss.CASES:
        entry = info['runtime_state'][0][section]
        if entry['type'] != 'SHT_NOBITS' or entry['size'] != size:
            raise ValueError('incorrect typed BSS section: ' + name)
        rows.append(dict(name=name, unit='runtime_state', input_section=section,
                         output_section='.runtime_bss.' + name, address=address,
                         size=size, actual_size=entry['size'], kind='zero_initialized_data'))
        placed.add(('runtime_state', section))
    for gap in state.ALIGNMENT_GAPS:
        rows.append(dict(**gap, unit="layout", input_section=None,
                         output_section=".layout." + gap["name"],
                         actual_size=gap["size"], kind="initialized_layout"))
    for name, address, size in ctr.CASES:
        rows.append(dict(name=name, unit="ctr", input_section=ctr.SECTION,
                         output_section=ctr.SECTION, address=address, size=size,
                         actual_size=info["ctr"][0][ctr.SECTION]["size"], kind="retained_metadata"))
        placed.add(("ctr", ctr.SECTION))
    for name, address, size in state.CASES:
        choices = [prefix + name for prefix in (".data.", ".rodata.", ".bss.")
                   if prefix + name in info["state"][0]]
        if len(choices) != 1:
            raise ValueError("state symbol must have one allocated section: " + name)
        section = choices[0]
        rows.append(dict(name=name, unit="state", input_section=section,
                         output_section=".state." + name, address=address, size=size,
                         actual_size=info["state"][0][section]["size"], kind="initialized_state"))
        placed.add(("state", section))
    for section in manifest["sections"]:
        name = section["name"]
        if name not in info["generated"][0]:
            continue  # Strings materialized only by the data-only test live in lookup pools.
        rows.append(dict(name=name, unit="generated", input_section=name, output_section=name,
                         address=section["address"], size=section["size"],
                         actual_size=info["generated"][0][name]["size"], kind="generated_data"))
        placed.add(("generated", name))
    for bridge in bridges.values():
        rows.append(dict(name=bridge["symbol"], unit="bridges", kind="linker_veneer",
                         input_section=".text." + bridge["symbol"],
                         output_section=".bridge.%08x" % bridge["address"],
                         address=bridge["address"], size=10, actual_size=10))

    # Unregistered allocated inputs must never fall into an accidental orphan
    # section or be discarded silently. ARM unwind metadata is not in stock's
    # corresponding reconstructed region and is tracked explicitly as omitted.
    omitted, stray, unused_library = [], [], []
    for unit, (sections, _) in info.items():
        for name, section in sections.items():
            if not section["size"] or not section["flags"] & 2 or (unit, name) in placed:
                continue
            if name.startswith((".ARM.exidx", ".ARM.extab")):
                omitted.append(dict(unit=unit, section=name, size=section["size"]))
            elif unit in sdk.LIBRARY_UNITS:
                unused_library.append(dict(unit=unit, section=name, size=section["size"]))
            else:
                # A body that is not yet stock's shape may pool a table stock
                # keeps inline; it gets a scratch home and is reported, never
                # painted into the image.
                stray.append(dict(unit=unit, section=name, size=section["size"]))
    sorted_rows = sorted(rows, key=lambda row: row["address"])
    overflow_rows, scratch = [], {True: 0x08100000, False: 0x00100000}
    for left, right in zip(sorted_rows, sorted_rows[1:]):
        align = max(left.get("input_align") or 1, 1)
        start = (left["address"] + align - 1) & -align  # the linker pads to the input alignment
        if start + left["actual_size"] > right["address"]:
            if not args.diagnostic_overflow or left["kind"] != "function":
                raise ValueError("compiled sections overlap: " + left["name"] + " / " + right["name"])
            overflow_rows.append(left)
    renames = {}
    for row in overflow_rows:
        flash = row["address"] >= 0x08000000
        row.update(stock_address=row["address"], overflow=True, address=scratch[flash])
        scratch[flash] += (row["actual_size"] + 15) & ~15
        renames.setdefault(row["unit"], []).append(row["name"])
    if overflow_rows:
        print("Overflowing bodies (linked at scratch addresses, callers bound to stock): "
              + ", ".join(f"{r['name']} ({r['actual_size']} > slot)" for r in overflow_rows))
    for unit, names in renames.items():
        renamed = out / (unit + ".overflow.o")
        subprocess.run([PREFIX + "objcopy", *[f"--redefine-sym={n}={n}__overflow" for n in names],
                        str(objects[unit]), str(renamed)], check=True)
        objects[unit] = renamed
    sorted_rows = sorted(rows, key=lambda row: row["address"])
    lines = ["/* Partial source integration, not a bootable firmware link. */", "SECTIONS {"]
    for row in sorted_rows:
        if row['kind'] == 'initialized_layout':
            lines.append(f'  {row["output_section"]} {row["address"]:#x} : '
                         + '{ FILL(0); BYTE(0); . = ALIGN(' + str(row['alignment']) + '); }')
            continue
        noload = ' (NOLOAD)' if row['kind'] == 'zero_initialized_data' else ''
        lines.append(f'  {row["output_section"]} {row["address"]:#x}{noload} : '
                     + '{ *(' + row["input_section"] + ') }')
    if stray:
        # Diagnostic only: a compiler that pools strings/constants differently
        # gets its stray sections a scratch home instead of aborting the sweep.
        lines.append("  . = 0x08200000;")
    for index, entry in enumerate(stray):
        lines.append(f"  .stray.{index} : {{ {objects[entry['unit']]}({entry['section']}) }}")
    if stray:
        print("Stray sections (not stock's shape, linked at scratch addresses): "
              + ", ".join(f"{e['unit']}:{e['section']} ({e['size']} bytes)" for e in stray))
    discards = " ".join(f"{objects[entry['unit']]}({entry['section']})" for entry in unused_library)
    lines += ["  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) " + discards + " }", "}"]
    needed = set()
    for obj in [*objects.values(), bridge_obj]:
        for name, entry in object_info(obj)[1].items():
            if entry["index"] == "SHN_UNDEF" and name not in definitions and not name.startswith("gd_bridge_"):
                needed.add(name)
    unknown = needed - addresses.keys()
    if unknown:
        raise ValueError("dependencies missing address evidence: " + ", ".join(sorted(unknown)))
    for name in sorted(needed):
        lines.append(f"{name} = {addresses[name]:#x}; /* UNRECOVERED dependency */")
    for row in overflow_rows:
        lines.append(f"{row['name']} = {row['stock_address'] | 1:#x}; /* OVERFLOW body linked at {row['address']:#x} */")
    script = out / "partial.ld"
    script.write_text("\n".join(lines) + "\n")
    elf_path = out / "partial.elf"
    subprocess.run([str(linker), *tc.FLAGS[:4], "-nostdlib", "-Wl,--entry=SystemInit",
                    "-Wl,-T," + str(script), "-Wl,-Map," + str(out / "partial.map"),
                    *map(str, objects.values()), str(bridge_obj), "-o", str(elf_path)], check=True)
    ram_region = next(region for region in layout["regions"]
                      if region["destination"] == 0x24000000 and region["kind"] == "decompress")
    ram, _ = decompress(stock[ram_region["source"] - 0x08000000:], ram_region["size"])
    rebuilt_ram = bytearray(len(ram))
    ram_coverage = bytearray(len(ram))
    with elf_path.open("rb") as stream:
        elf = ELFFile(stream)
        for row in rows:
            section = elf.get_section_by_name(row["output_section"])
            if section["sh_addr"] != row["address"]:
                raise ValueError("wrong linked address: " + row["name"])
            if row.get('overflow'):
                pass
            elif row['kind'] in ('function', 'runtime_assembly'):
                symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(row['name'])
                if len(symbols or []) != 1 or symbols[0]['st_value'] & ~1 != row['address']:
                    if not args.diagnostic_overflow:
                        raise ValueError('function entry shifted by input alignment: ' + row['name'])
                    row['entry_shifted'] = True
            elif row['kind'] == 'constant_data' and row.get('generated'):
                if section['sh_type'] != 'SHT_PROGBITS' or section['sh_flags'] & 7 != 2:
                    raise ValueError('compiler table is not read-only data: ' + row['name'])
            elif row['kind'] == 'constant_data':
                symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(row['name'])
                if (len(symbols or []) != 1 or symbols[0]['st_value'] != row['address']
                        or symbols[0]['st_info']['type'] != 'STT_OBJECT'
                        or symbols[0]['st_size'] != row['size']
                        or section['sh_type'] != 'SHT_PROGBITS' or section['sh_flags'] & 7 != 2):
                    raise ValueError('constant object ABI/layout differs: ' + row['name'])
            actual = section.data()
            if 0x24000000 <= row["address"] < 0x24000000 + len(ram):
                offset = row["address"] - 0x24000000
                expected = ram[offset:offset + row["size"]]
                if len(actual) != row['size'] or any(ram_coverage[offset:offset + len(actual)]):
                    raise ValueError('initialized RAM overlap or wrong section size: ' + row['name'])
                rebuilt_ram[offset:offset + len(actual)] = actual
                ram_coverage[offset:offset + len(actual)] = bytes([1]) * len(actual)
            elif row['kind'] == 'zero_initialized_data':
                if section['sh_type'] != 'SHT_NOBITS':
                    raise ValueError('zero-initialized storage acquired load bytes: ' + row['name'])
                expected = bytes(row['size'])
            else:
                address = row.get("stock_address", row["address"])
                offset = address + 0x4418 if address < 0x08000000 else address - 0x08000000
                expected = stock[offset:offset + row["size"]]
            row.update(exact=actual == expected and not row.get('entry_shifted'), actual_size=len(actual),
                       matching_bytes=sum(a == b for a, b in zip(actual, expected)),
                       expected_sha256=hashlib.sha256(expected).hexdigest(),
                       actual_sha256=hashlib.sha256(actual).hexdigest())
    if not all(ram_coverage):
        raise ValueError('initialized RAM still has bytes without source or explicit layout coverage')
    (out / 'initialized-ram.bin').write_bytes(rebuilt_ram)
    source_files = {SOURCE / filename for filename, _ in units.values()}
    source_files.update(dependencies)
    source_files.update(Path(profile.__file__).resolve() for profile in (
        tc, motor, core, gpio, generated, serial, base, protocol, runtime,
        bss, stepper, mpu, board, state, ctr, trsync, gpio_output, memory,
        irqs, adc_irqs, dma_irqs, endstop, math, hardware, scatter_runtime,
        adc_vendor, digital_out, angles, protocol_data, scatter_handlers, *new_profiles))
    source_files.update(ROOT / 'tools' / filename for filename in (
        'extract-gd-layout.py', 'gd_function_gate.py', 'scatterload.py'))
    source_files.update(SOURCE.rglob("*.h"))
    source_files.update((Path(__file__).resolve(), asm))
    report = dict(scope="partial source integration with explicit missing dependencies; NOT bootable",
                  whole_image_verified=False, compiler=str(cc), flags=flags, commands=commands,
                  compiler_sha256=hashlib.sha256(cc.read_bytes()).hexdigest(),
                  stock_md5=layout["stock_md5"], linked_elf=str(elf_path),
                  linked_elf_sha256=hashlib.sha256(elf_path.read_bytes()).hexdigest(),
                  initialized_ram=dict(path=str(out / 'initialized-ram.bin'), size=len(ram),
                                       exact=rebuilt_ram == ram,
                                       expected_sha256=hashlib.sha256(ram).hexdigest(),
                                       actual_sha256=hashlib.sha256(rebuilt_ram).hexdigest()),
                  source_sha256={source_name(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(source_files)},
                  external_dependencies=[dict(name=name, address=addresses[name],
                                              kind="unrecovered_data" if name in {
                                                  'encode_acknak', 'generated_string_00006dc2'} else
                                              "layout_symbol" if name in {
                                                  'gd_initial_sp', 'gd_boot_ram_base',
                                                  'gd_scatter_table', 'gd_scatter_table_end'} else
                                              "mmio" if addresses[name] >= 0x40000000 else
                                              "unrecovered_ram" if addresses[name] >= 0x24000000 else "unrecovered_code")
                                         for name in sorted(needed)],
                  zero_initialized_storage=dict(typed_bytes=sum(c[2] for c in bss.CASES),
                                                unknown_intervals=bss.holes()),
                  standalone_exclusions=standalone_exclusions,
                  semantic_reference_exclusions=semantic_reference_exclusions,
                  routed_references=rewrites, bridges=list(bridges.values()),
                  omitted_unwind_sections=omitted, unused_library_sections=unused_library,
                  overflow_rows=[row["name"] for row in overflow_rows],
                  stray_sections=stray, results=rows)
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    for kind in ("function", "runtime_assembly", "generated_data", "constant_data", "platform_data", "initialized_state", "zero_initialized_data", "initialized_layout", "retained_metadata", "vectors", "linker_veneer"):
        subset = [row for row in rows if row["kind"] == kind]
        exact = [row for row in subset if row["exact"]]
        print(f"{kind}: {len(exact)}/{len(subset)} entire sections exact, "
              f"{sum(row['size'] for row in exact)} exact-span bytes")
    print(f"Actual shared definitions: {len(definitions)}; external symbol bindings: {len(needed)}")
    for kind in ("unrecovered_code", "unrecovered_data", "unrecovered_ram", "mmio", "layout_symbol"):
        subset = [row for row in report["external_dependencies"] if row["kind"] == kind]
        print(f"  {kind}: {len(subset)} names at {len({row['address'] for row in subset})} unique addresses")
    print("Partial ELF: " + str(elf_path) + "; whole-image equality NOT VERIFIED")
    print(f'Complete source-built initialized RAM: {len(rebuilt_ram)} bytes, '
          + ('EXACT' if rebuilt_ram == ram else 'DIFF'))
    # C-body differences are expected at this stage. Data, vectors and generic
    # bridge construction are established integration invariants, not optional.
    return int(any(not row["exact"] for row in rows if row["kind"] != "function"))


if __name__ == "__main__":
    raise SystemExit(main())
