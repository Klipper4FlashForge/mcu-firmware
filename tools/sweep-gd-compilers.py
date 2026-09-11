#!/usr/bin/env python3
"""Score the mainBoardGD reconstruction under several LLVM releases at once.

For each compiler this runs the partial link in diagnostic mode (bodies that
overrun their stock slot are linked in a scratch region instead of aborting),
the scatter build and the whole-image comparison, then prints one row per
compiler and a per-function table of matching bytes. The table is what says
which compiler generation the stock image came from: a function that is exact
under one release and not another is evidence about the compiler, not the
source.

Compilers are given as label=path/to/clang. Releases before 16 need the libc
headers named explicitly; releases before 14 lack -falign-loops and the
elementwise builtins, which are replaced by their scalar names. Those
adjustments are per-release toolchain compatibility, not per-function options.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / 'work/atfe/shim'
LINKER = ROOT / 'work/atfe/ATfE-22.1.0-Linux-x86_64/bin/clang'  # GNU-script-capable link driver for armclang runs
CMSIS_ARMCLANG = ROOT / 'work/cmsis-armclang/cmsis_armclang.h'
HEADERS = ROOT / 'work/atfe/LLVMEmbeddedToolchainForArm-13.0.0/lib/clang-runtimes/armv7em_hard_fpv4_sp_d16/include'


def version_of(cc):
    text = subprocess.run([cc, '--version'], capture_output=True, text=True,
                          env=environment()).stdout
    match = re.search(r'(?:clang version|Arm Compiler for Embedded) (\d+)\.(\d+)(?:\.(\d+))?', text)
    if match and match.group(3) is None:
        return (int(match.group(1)), int(match.group(2)), 0, 'armclang')
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def environment():
    env = dict(os.environ)
    if SHIM.exists():  # stub libtinfo.so.5 for the 2021-2023 releases
        env['LD_LIBRARY_PATH'] = str(SHIM) + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    return env


def run_one(label, cc, extra, out):
    version = version_of(cc)
    cflags = ['--cflag=-fomit-frame-pointer', *extra]
    if Path(cc).name.startswith('armclang'):
        # Klipper's CMSIS import carries only cmsis_gcc.h; stock's compiler
        # took the same CMSIS 5.7.0 release's cmsis_armclang.h.
        if not CMSIS_ARMCLANG.exists():
            CMSIS_ARMCLANG.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['curl', '-sL', '-o', str(CMSIS_ARMCLANG),
                            'https://raw.githubusercontent.com/ARM-software/CMSIS_5/5.7.0/'
                            'CMSIS/Core/Include/cmsis_armclang.h'], check=True)
        cflags += ['--linker', str(LINKER), '--cflag=-I' + str(CMSIS_ARMCLANG.parent)]
    upstream = len(version) == 3  # armclang reports its own version scheme
    if upstream and version < (16, 0, 0):  # no default sysroot headers in the 13-15 packages
        cflags += ['--cflag=-isystem', '--cflag=' + str(HEADERS)]
    if upstream and version < (14, 0, 0):
        cflags += ['--cflag=-Wno-ignored-optimization-argument',
                   '--cflag=-D__builtin_elementwise_trunc=__builtin_truncf']
    out.mkdir(parents=True, exist_ok=True)
    log = out / 'sweep.log'
    with log.open('w') as stream:
        steps = [
            ['python3', 'tools/build-gd-partial.py', '--diagnostic-overflow', '--cc', cc,
             '--out', str(out / 'partial'), *cflags],
            ['python3', 'tools/build-gd-scatter.py', '--partial', str(out / 'partial/results.json'),
             '--out', str(out / 'scatter')],
            ['python3', 'tools/build-gd-image.py', '--elf', str(out / 'partial/partial.elf'),
             '--scatter', str(out / 'scatter/scatter-data.bin'), '--out', str(out / 'image'),
             '--limit', '0']]
        for step in steps:
            stream.write('$ ' + ' '.join(step) + '\n')
            stream.flush()
            result = subprocess.run(step, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                    env=environment())
            if result.returncode and not (out / 'partial/results.json').exists():
                return dict(label=label, version=version, error='see ' + str(log))
    rows = [r for r in json.loads((out / 'partial/results.json').read_text())['results']
            if r['kind'] == 'function']
    image = json.loads((out / 'image/results.json').read_text())
    return dict(label=label, version=version, cc=cc,
                exact=sum(r['exact'] for r in rows),
                matching_bytes=sum(r['matching_bytes'] for r in rows),
                fits=sum(r['actual_size'] <= r['size'] for r in rows),
                functions=len(rows), image_differing=image['differing_bytes'],
                rows={r['name']: (r['exact'], r['matching_bytes'], r['actual_size'], r['size'])
                      for r in rows})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compilers', nargs='+', help='label=path/to/clang')
    parser.add_argument('--cflag', action='append', default=[],
                        help='extra global flag for every compiler (passed through)')
    parser.add_argument('--no-compat', action='store_true')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/gd-sweep')
    parser.add_argument('--table', action='store_true', help='print the per-function table')
    args = parser.parse_args()
    extra = ['--cflag=' + flag for flag in args.cflag] + (['--no-compat'] if args.no_compat else [])
    results = []
    for spec in args.compilers:
        label, _, cc = spec.partition('=')
        results.append(run_one(label, str(Path(cc).resolve()), extra, args.out / label))
        r = results[-1]
        if 'error' in r:
            print(f"{label:24} FAILED ({r['error']})")
        else:
            print(f"{label:24} {'.'.join(map(str, r['version'][:3])):8} exact {r['exact']:3}/{r['functions']}"
                  f"  matching bytes {r['matching_bytes']:6}  fits {r['fits']:3}"
                  f"  whole-image differing {r['image_differing']:6}")
    good = [r for r in results if 'error' not in r]
    (args.out / 'summary.json').write_text(json.dumps(good, indent=1) + '\n')
    if args.table and good:
        names = sorted(good[0]['rows'])
        print('\n' + ' ' * 36 + ' '.join(r['label'][:9].ljust(9) for r in good))
        for name in names:
            cells = [r['rows'][name] for r in good]
            if all(c[0] for c in cells):
                continue
            print(f'{name:36}' + ' '.join('  EXACT  ' if c[0] else f'{c[1]:>4}/{c[2]:<4}' for c in cells))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
