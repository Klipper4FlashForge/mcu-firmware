#!/usr/bin/env python3
"""Run mainBoardGD's isolated recovery gates with one global configuration.

Runs every gate even when a previous comparison fails. Exit zero requires all
requested gates to pass, but NEVER establishes whole-image equality: these
checks still bind unrecovered symbols to observed addresses.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ["-mllvm", "-arm-promote-constant", "-fno-unroll-loops", "-falign-loops=4",
         "-mllvm", "-enable-shrink-wrap=false", "-fno-builtin",
         "-mllvm", "-align-all-functions=1"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", help="ATfE clang (otherwise discover retained installation)")
    parser.add_argument("--out", type=Path, default=ROOT / "work/mainBoardGD-recovery.json")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("gd_toolchain", ROOT / "tools/check-gd-toolchain.py")
    tc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tc)
    cc = str(tc.compiler_path(args.cc))
    flags = ["--cflag=" + flag for flag in FLAGS]
    gates = [
        ("probes", "check-gd-toolchain.py", ["--cc", cc, *flags]),
        ("motor", "check-gd-motor.py", ["--cc", cc, *flags,
                                        "--out", "work/mainBoardGD-motor", "--require-all"]),
        ("motor_reset_model", "check-gd-motor-reset-model.py", []),
        ("pi_model", "check-gd-pi-model.py", []),
        ("pwm_update_model", "check-gd-pwm-update-model.py", []),
        ("motor_step_model", "check-gd-motor-step-model.py", []),
        ("loop_b_model", "check-gd-loop-b-model.py", []),
        ("core", "check-gd-core.py", ["--cc", cc, *flags,
                                      "--out", "work/mainBoardGD-core", "--require-all"]),
        # GPIO uses this same configuration as its explicit defaults.
        ("gpio", "check-gd-gpio.py", ["--cc", cc, "--out", "work/mainBoardGD-gpio"]),
        ("serial", "check-gd-serial.py", ["--cc", cc]),
        ("base", "check-gd-base.py", ["--cc", cc]),
        ("stats_model", "check-gd-stats-model.py", []),
        ("protocol", "check-gd-protocol.py", ["--cc", cc]),
        ("stepper", "check-gd-stepper.py", ["--cc", cc]),
        ("stepper_load_model", "check-gd-stepper-load-model.py", []),
        ("trsync", "check-gd-trsync.py", ["--cc", cc]),
        ("irqs", "check-gd-irqs.py", ["--cc", cc]),
        ("adc_irqs", "check-gd-adc-irqs.py", ["--cc", cc]),
        ("dma_irqs", "check-gd-dma-irqs.py", ["--cc", cc]),
        ("endstop", "check-gd-endstop.py", ["--cc", cc]),
        ("math", "check-gd-math.py", ["--cc", cc]),
        ("sqrt_model", "check-gd-sqrt-model.py", []),
        ("dq_limit_model", "check-gd-dq-limit-model.py", []),
        ("hardware", "check-gd-hardware.py", ["--cc", cc]),
        ("adc_vendor", "check-gd-adc-vendor.py", ["--cc", cc]),
        ("adc_vendor_behavior", "check-gd-adc-vendor.py", ["--self-test"]),
        ("digital_out", "check-gd-digital-out.py", ["--cc", cc]),
        ("angles", "check-gd-angles.py", ["--cc", cc]),
        ("angle_data", "check-gd-angle-data.py", ["--cc", cc]),
        ("dma_vendor", "check-gd-dma-vendor.py", ["--cc", cc]),
        ("interrupt_control", "check-gd-interrupt-control.py", ["--cc", cc]),
        ("dma_control_mmio", "check-gd-dma-control-mmio.py", []),
        ("analog_in", "check-gd-analog-in.py", ["--cc", cc]),
        ("buttons", "check-gd-buttons.py", ["--cc", cc]),
        ("trig", "check-gd-trig.py", ["--cc", cc]),
        ("trig_data", "check-gd-trig-data.py", ["--cc", cc]),
        ("trig_model", "check-gd-trig-model.py", []),
        ("timer_vendor", "check-gd-timer-vendor.py", ["--cc", cc]),
        ("timer_data", "check-gd-timer-data.py", ["--cc", cc]),
        ("timer_vendor_model", "check-gd-timer-vendor.py", ["--self-test"]),
        ("config_finalize", "check-gd-config-finalize.py", ["--cc", cc]),
        ("config_finalize_model", "check-gd-config-finalize-model.py", []),
        ("pwm_vendor", "check-gd-pwm-vendor.py", ["--cc", cc]),
        ("pwm_vendor_model", "check-gd-pwm-vendor.py", ["--self-test"]),
        ("debug_scope", "check-gd-debug-scope.py", ["--cc", cc]),
        ("debug_scope_data", "check-gd-debug-scope-data.py", ["--cc", cc]),
        ("protocol_data", "check-gd-protocol-data.py", ["--cc", cc]),
        ("platform_data", "check-gd-platform-data.py", ["--cc", cc]),
        ("scatter_runtime", "check-gd-scatter-runtime.py", ["--cc", cc]),
        ("scatter_runtime_model", "check-gd-scatter-runtime-model.py", []),
        ("gpio_output", "check-gd-gpio-output.py", ["--cc", cc]),
        ("gpio_output_mmio", "check-gd-gpio-output-mmio.py", []),
        ("memory", "check-gd-memory.py", ["--cc", cc]),
        ("memory_behavior", "check-gd-memory.py", ["--self-test"]),
        ("mpu", "check-gd-mpu.py", ["--cc", cc]),
        ("board", "check-gd-board.py", ["--cc", cc]),
        ("state", "check-gd-state.py", ["--cc", cc]),
        ("runtime_assembly", "check-gd-runtime.py", ["--cc", cc]),
        ("scatter_handlers", "check-gd-scatter-handlers.py", ["--cc", cc]),
        ("scatter_handlers_model", "check-gd-scatter-runtime-model.py",
         ["--isolated-report", "work/mainBoardGD-scatter-handlers/results.json",
          "--out", "work/mainBoardGD-scatter-handlers-model.json"]),
        ("runtime_storage", "check-gd-bss.py", ["--cc", cc]),
        ("retained_ctr", "emit-gd-ctr.py", ["--cc", cc, "--check", "--verify",
                                             "--report", "work/mainBoardGD-ctr.json"]),
        ("generated", "emit-gd-generated.py", ["--check", "--verify", "--verify-lookups",
                                                "--verify-runners", "--verify-combined",
                                                "--report", "work/mainBoardGD-generated-verification.json",
                                                "--compiler", cc, *flags]),
        ("startup", "check-gd-startup.py", ["--cc", cc, *flags]),
        ("partial_integration", "build-gd-partial.py", ["--cc", cc]),
        ("partial_parity", "check-gd-partial-parity.py", []),
        ("peripheral_irqs_mmio", "check-gd-peripheral-irqs-mmio.py", []),
        ("board_mmio", "check-gd-board-mmio.py", []),
        ("scatter_compression", "gd_scatter_compress.py", []),
        ("scatter_load_data", "build-gd-scatter.py", []),
    ]
    rows = []
    for name, tool, options in gates:
        print(f"\n{name} gate", flush=True)
        command = [sys.executable, str(ROOT / "tools" / tool), *options]
        result = subprocess.run(command, cwd=ROOT)
        rows.append(dict(name=name, command=command, returncode=result.returncode,
                         passed=result.returncode == 0))
    # The startup checker separates successful MMIO models from byte equality.
    startup_path = ROOT / "work/mainBoardGD-startup.json"
    report = dict(scope="isolated source/data gates, not a complete firmware build",
                  whole_image_verified=False, compiler=cc, global_compatibility_flags=FLAGS,
                  source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted((ROOT / "mcu/mainBoardGD/recovered").rglob("*"))
                                 if path.is_file() and path.suffix in (".c", ".h", ".ld", ".S")},
                  startup_detail=str(startup_path), gates=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    passed = sum(row["passed"] for row in rows)
    print(f"\n{passed}/{len(rows)} gate processes passed; details: {args.out}")
    print("Startup process success means MMIO scenarios passed; inspect its byte_exact fields.")
    print("Board MMIO success means modeled accesses/barriers match, with two external handoffs mocked.")
    print("Partial integration success means an audited link, not that all sections match stock.")
    print("Whole-image equality: NOT VERIFIED.")
    return int(passed != len(rows))


if __name__ == "__main__":
    raise SystemExit(main())
