#!/usr/bin/env python3
"""Compile/link isolated motor functions at stock addresses and compare all bytes.

This is a function gate, not a whole-image build. External code symbols bind to
stock ITCM veneers, and the motor pointer table binds to its stock RAM address.
Function sections include their literal pools; shorter prefixes never count as
exact. No stock bytes are used as candidate source or linker input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("command_config_mclib", 0xE40, 196, False),
    ("command_mclib_config_microstep", 0x18A8, 36, False),
    ("command_mclib_config_stalldetect", 0x18D0, 48, False),
    ("command_mclib_identify_motor", 0x1900, 14, False),
    ("command_mclib_set_current", 0x1910, 76, False),
    ("command_mclib_set_pid_params", 0x1960, 72, False),
    ("command_mclib_set_resonance_damp", 0x19A8, 96, False),
    ("mclib_set_microstep", 0x080015B8, 40, True),
    ("mclib_set_run_current", 0x08001220, 52, True),
    ("mclib_set_hold_current", 0x08001178, 56, True),
    ("mclib_pi_step", 0x080020D0, 116, True),
    ("mclib_pi_reset", 0x08002148, 10, True),
    ("mclib_park", 0x080020B0, 26, True),
    ("mclib_observer_reset", 0x08002C48, 14, True),
    ("mclib_motor_reset", 0x080011B0, 110, True),
    ("mclib_init", 0x3D00, 212, False),
    ("mclib_pwm_disable", 0x3AD8, 48, False),
    ("mclib_current_acquisition_reset", 0x39E0, 50, False),
    ("mclib_sample_filter_init", 0x08000B28, 12, True),
    ("mclib_sample_filter_update", 0x08000B10, 20, True),
    ("mclib_timer_start", 0x08002E18, 12, True),
    ("mclib_current_acquisition_calibrate", 0x3A18, 68, False),
    ("mclib_pwm_update", 0x3B38, 228, False),
    ("mclib_pwm_prepare", 0x08002E28, 164, True),
    ("mclib_control_loop_b", 0x08001258, 860, True),
    ("mclib_control_loop_a", 0x08000C30, 1352, True),
    ("mclib_gpio_direction", 0x08000B78, 6, True),
    ("mclib_gpio_disable", 0x08000B80, 52, True),
    ("mclib_gpio_enable", 0x08000BB8, 120, True),
    ("mclib_gpio_step", 0x08001670, 156, True),
]
# Reset calls the separately compiled math helpers. No per-function inlining
# attributes or compiler options are needed to retain those source boundaries.
UNITS = {"commands": None, "helpers": "MCLIB_FLASH_HELPERS",
         "reset": "MCLIB_RESET_HELPER", "io": "MCLIB_IO_HELPERS",
         "calibration": "MCLIB_CALIBRATE",
         "registers": "MCLIB_REGISTER_HELPERS",
         "loop_b": "MCLIB_CONTROL_LOOP_B", "loop_a": "MCLIB_CONTROL_LOOP_A",
         "gpio_hooks": "MCLIB_GPIO_HOOKS"}
CASE_UNITS = {name: ("gpio_hooks" if name.startswith("mclib_gpio_") else
                    "loop_a" if name == "mclib_control_loop_a" else
                    "loop_b" if name == "mclib_control_loop_b" else
                    "reset" if name == "mclib_motor_reset" else
                    "calibration" if name == "mclib_current_acquisition_calibrate" else
                    "registers" if name in ("timer_channel_output_state_config",
                                            "mclib_sample_filter_init",
                                            "mclib_sample_filter_update",
                                            "mclib_timer_start") else
                    "io" if name in ("mclib_pwm_disable",
                                     "mclib_pwm_update",
                                     "mclib_current_acquisition_reset",
                                     "timer_enable") else
                    "helpers" if flash else "commands")
              for name, _, _, flash in CASES}
SYMBOLS = {
    "oid_alloc": 0x3F31, "oid_lookup": 0x3FD9,
    "mclib_motors": 0x24002504,
    "command_config_mclib": 0xE41,
    "mclib_set_microstep": 0x5B63,
    "mclib_set_run_current": 0x5B6D,
    "mclib_set_hold_current": 0x5B77,
    "mclib_motor_reset": 0x5C0D,
    "mclib_hardware_init": 0x5C03,
    "mclib_timer_start": 0x5C17,
    "mclib_observer_reset": 0x08002C49,
    "mclib_pi_reset": 0x08002149,
    "mclib_pwm_disable": 0x08003199,
    "mclib_pwm_enable": 0x080031A3,
    "mclib_gpio_direction": 0x5B9F,
    "mclib_gpio_step": 0x5BA9,
    "mclib_gpio_disable": 0x5BB3,
    "mclib_gpio_enable": 0x5BBD,
    "mclib_current_acquisition_reset": 0x080031CB,
    "timer_channel_output_state_config": 0x4E39,
    "mclib_sample_filter_init": 0x5BEF,
    "mclib_sample_filter_update": 0x5BF9,
    "timer_enable": 0x08003351,
    "mclib_current_acquisition_calibrate": 0x3A19,
    "mclib_pwm_update": 0x080031B7,
    "mclib_pwm_prepare": 0x08002E29,
    "mclib_control_loop_b": 0x5B27,
    "mclib_control_loop_a": 0x5B1D,
    "mclib_current_acquisition_read": 0x080031AD,
    "mclib_current_acquisition_set_polarity": 0x080031C1,
    "mclib_observer_update": 0x08002C59,
    "mclib_sincos": 0x08002971,
    "mclib_limit_dq_voltage": 0x080015E1,
    "mclib_inverse_park": 0x08002951,
    "mclib_park": 0x080020B1,
    "mclib_pi_step": 0x080020D1,
    "mclib_sine": 0x08002B51,
    "mclib_sqrt_positive": 0x08002DF9,
    "mclib_motor_x": 0x2400282C,
    "mclib_motor_y": 0x24002514,
    "mclib_motor_z": 0x24002B44,
    "mclib_motor_extruder": 0x240021EC,
}


def section(path, wanted):
    data = path.read_bytes()
    if data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError(f"{path}: expected ELF32 little endian")
    offset = struct.unpack_from("<I", data, 32)[0]
    size, count, strings_index = struct.unpack_from("<3H", data, 46)
    headers = [struct.unpack_from("<10I", data, offset + i * size)
               for i in range(count)]
    strings_header = headers[strings_index]
    strings = data[strings_header[4]:strings_header[4] + strings_header[5]]
    for header in headers:
        name = strings[header[0]:].split(b"\0", 1)[0].decode()
        if name == wanted:
            return header[3], data[header[4]:header[4] + header[5]]
    raise ValueError(f"{path}: section {wanted} not found")


def run(argv):
    subprocess.run([str(x) for x in argv], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", required=True, type=Path, help="ATfE clang executable")
    parser.add_argument("--out", type=Path, help="keep objects, links and JSON here")
    parser.add_argument("--source", type=Path,
                        default=ROOT / "mcu/mainBoardGD/recovered/mclib_commands.c")
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument("--promote-constant", action="store_true",
                        help="apply candidate global -mllvm -arm-promote-constant")
    parser.add_argument("--cflag", action="append", default=[],
                        help="candidate global compile flag, applied to ALL units")
    args = parser.parse_args()
    scratch = None
    if args.out is None:
        scratch = tempfile.TemporaryDirectory(prefix="gd-motor-")
        out = Path(scratch.name)
    else:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=True)
    cc = args.cc.resolve()
    source = args.source.resolve()
    target = ["--target=arm-none-eabi", "-mcpu=cortex-m7", "-mfpu=fpv5-d16",
              "-mfloat-abi=hard"]
    flags = [*target, "-O2", "-ffunction-sections", "-fdata-sections",
             "-Wall", "-Wextra", "-Werror",
             *(["-mllvm", "-arm-promote-constant"] if args.promote_constant else []),
             *args.cflag]
    commands = []
    source_paths = {source, Path(__file__).resolve()}
    compiler_version = subprocess.check_output([str(cc), "--version"], text=True)
    compiler_sha256 = hashlib.sha256(cc.read_bytes()).hexdigest()
    for unit, macro in UNITS.items():
        obj = out / (unit + ".o")
        dependency_file = obj.with_suffix(".d")
        command = [str(cc), *flags,
                   *(["-D" + macro] if macro else []),
                   "-MMD", "-MF", str(dependency_file), "-MT", "motor_dependencies",
                   "-c", str(source), "-o", str(obj)]
        run(command)
        commands.append(command)
        # Hash the headers the compiler actually used, including a custom
        # --source's local header, rather than assuming its include directory.
        dependencies = dependency_file.read_text().replace("\\\n", " ")
        source_paths.update(Path(name).resolve() for name in
                            shlex.split(dependencies.split(":", 1)[1]))
    source_sha256 = {}
    for path in sorted(source_paths):
        try:
            name = str(path.relative_to(ROOT))
        except ValueError:
            name = str(path)
        source_sha256[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    stock = (ROOT / "mcu/mainBoardGD/stock/mainBoardGD.bin").read_bytes()
    if hashlib.md5(stock).hexdigest() != "fb64911bac422a27d7ed7fab3597603f":
        raise ValueError("stock image differs from the mainBoardGD recovery target")
    rows = []
    for name, address, expected_length, flash in CASES:
        linker = out / (name + ".ld")
        definitions = "\n".join(f"{key} = 0x{value:x};"
                                for key, value in SYMBOLS.items() if key != name)
        linker.write_text(definitions + f"\nSECTIONS {{\n"
                          f"  .text 0x{address:x} : {{ *(.text.{name}) }}\n"
                          "  /DISCARD/ : { *(.text*) *(.ARM.exidx*) *(.ARM.extab*) }\n"
                          "}\n")
        elf = out / (name + ".elf")
        obj = out / (CASE_UNITS[name] + ".o")
        run([cc, *target, "-nostdlib", f"-Wl,--entry={name}",
             f"-Wl,-T,{linker}", obj, "-o", elf])
        actual_address, candidate = section(elf, ".text")
        if actual_address != address:
            raise ValueError(f"{name}: linked at wrong address {actual_address:#x}")
        stock_offset = address - 0x08000000 if flash else address + 0x4418
        expected = stock[stock_offset:stock_offset + expected_length]
        if len(expected) != expected_length:
            raise ValueError(f"{name}: stock range outside image")
        exact = candidate == expected
        matches = sum(a == b for a, b in zip(candidate, expected))
        prefix = next((i for i, (a, b) in enumerate(zip(candidate, expected))
                       if a != b), min(len(candidate), len(expected)))
        row = dict(name=name, address=address, expected_size=expected_length,
                   actual_size=len(candidate), matching_bytes=matches,
                   prefix=prefix, exact=exact,
                   expected_sha256=hashlib.sha256(expected).hexdigest(),
                   candidate_sha256=hashlib.sha256(candidate).hexdigest())
        rows.append(row)
        print(f"{name:39s} {address:#010x} "
              f"size={len(candidate)}/{expected_length} bytes={matches}/{expected_length} "
              f"prefix={prefix} {'EXACT' if exact else 'DIFF'}")
    exact_rows = [row for row in rows if row["exact"]]
    print(f"{len(exact_rows)}/{len(rows)} exact functions; "
          f"{sum(row['expected_size'] for row in exact_rows)}/"
          f"{sum(row['expected_size'] for row in rows)} bytes in exact functions. "
          "Isolated stock-address links, not a whole-firmware match.")
    if args.out is not None:
        report = dict(
            scope="isolated stock-address motor links, not whole firmware",
            stock_md5=hashlib.md5(stock).hexdigest(), compiler=str(cc),
            compiler_sha256=compiler_sha256, compiler_version=compiler_version.strip(),
            flags=flags, commands=commands, source_sha256=source_sha256,
            results=rows)
        (out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    if scratch is not None:
        scratch.cleanup()
    return 1 if args.require_all and len(exact_rows) != len(rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
