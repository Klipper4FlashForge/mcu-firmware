#!/usr/bin/env python3
"""Gate complete source-derived FlashForge/core functions, including pools.

External symbols bind to measured stock addresses for this isolated test.
This is not an integrated firmware build; no stock code is linked as input.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


tc = module("gd_toolchain", ROOT / "tools/check-gd-toolchain.py")
motor = module("gd_motor", ROOT / "tools/check-gd-motor.py")
CASES = [
    ("gd_system_reset", 0x288, 36, "core"),
    ("command_get_basic_param", 0x1690, 52, "ff_commands"),
    ("command_get_mcu_version", 0x1778, 68, "ff_commands"),
    ("command_get_pa", 0x17c0, 48, "ff_commands"),
    ("command_pa_action", 0x1a08, 26, "ff_commands"),
    ("command_remove_peel", 0x1c18, 2, "ff_commands"),
    ("command_reset", 0x1c20, 4, "ff_commands"),
    ("initial_pins_setup", 0x3878, 2, "core"),
    ("irq_disable", 0x3880, 4, "core"),
    ("irq_enable", 0x3888, 4, "core"),
    ("irq_poll", 0x3890, 2, "core"),
    ("irq_restore", 0x3898, 6, "core"),
    ("irq_save", 0x38a0, 8, "core"),
    ("irq_wait", 0x38a8, 8, "core"),
    ("timer_cnt_init", 0x4ec8, 94, "timer"),
    ("timer_is_before", 0x5518, 6, "core"),
    ("timer_kick", 0x5520, 24, "core"),
    ("timer_read_time", 0x5580, 12, "core"),
    ("timer_reset", 0x5590, 14, "timer"),
    ("timer_wrap_event", 0x5898, 16, "timer"),
]
SYMBOLS = {"ctr_lookup_encoder": 0x21a1, "command_sendf": 0x1ca9,
           "ff_pa_value": 0x2400883c, "ff_pa_action": 0x24008838,
           "ff_pa_pc": 0x24008834, "gd_system_reset": 0x289,
           "wrap_timer": 0x24002e78, "sched_add_timer": 0x40a1,
           "irq_save": 0x38a1, "irq_restore": 0x3899}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc")
    parser.add_argument("--cflag", action="append", default=[])
    parser.add_argument("--out", type=Path, default=ROOT / "work/mainBoardGD-core")
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    cc = tc.compiler_path(args.cc)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stock = tc.STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != tc.STOCK_MD5:
        raise ValueError("unexpected stock image")
    commands = []
    for unit in sorted({row[3] for row in CASES}):
        source = ROOT / "mcu/mainBoardGD/recovered" / (unit + ".c")
        command = [str(cc), *tc.FLAGS, *args.cflag,
                   "-I" + str(ROOT / "klipper/lib/cmsis-core"),
                   "-c", str(source), "-o", str(out / (unit + ".o"))]
        subprocess.run(command, check=True)
        commands.append(dict(argv=command, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    rows = []
    for name, address, size, unit in CASES:
        ld = out / (name + ".ld")
        ld.write_text("\n".join(f"{key} = {value:#x};" for key, value in SYMBOLS.items()
                                if key != name)
                      + f"\nSECTIONS {{ .text {address:#x} : {{ *(.text.{name}) }}\n"
                      + " /DISCARD/ : { *(.text*) *(.ARM.exidx*) *(.ARM.extab*) } }\n")
        elf = out / (name + ".elf")
        subprocess.run([str(cc), *tc.FLAGS[:4], "-nostdlib", f"-Wl,--entry={name}",
                        f"-Wl,-T,{ld}", str(out / (unit + ".o")), "-o", str(elf)], check=True)
        actual_address, candidate = motor.section(elf, ".text")
        if actual_address != address:
            raise ValueError("incorrect section address")
        expected = stock[address + 0x4418:address + 0x4418 + size]
        exact = candidate == expected
        matches = sum(a == b for a, b in zip(candidate, expected))
        rows.append(dict(name=name, address=address, expected_size=size,
                         actual_size=len(candidate), matching_bytes=matches, exact=exact,
                         expected_sha256=hashlib.sha256(expected).hexdigest(),
                         actual_sha256=hashlib.sha256(candidate).hexdigest()))
        print(f"{name:28} {matches}/{size} bytes, size={len(candidate)} "
              + ("EXACT" if exact else "DIFF"))
    exact = [row for row in rows if row["exact"]]
    print(f"{len(exact)}/{len(rows)} exact functions; "
          f"{sum(row['expected_size'] for row in exact)} bytes in exact functions.")
    (out / "results.json").write_text(json.dumps(dict(
        scope="isolated stock-address links, not whole firmware", commands=commands,
        stock_md5=tc.STOCK_MD5, results=rows), indent=2) + "\n")
    return 1 if args.require_all and len(exact) != len(rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
