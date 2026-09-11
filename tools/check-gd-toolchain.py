#!/usr/bin/env python3
"""Compile four mainBoardGD source probes and compare entire code sections.

    python3 tools/check-gd-toolchain.py --cc /path/to/clang

Compiler selection: --cc, MCU_GD_CC, a clang under work/atfe, then the
user-supplied temporary ATfE installation if it still exists. Output defaults
to work/mainBoardGD-toolchain.json. Comparisons include literal pools and
reject unresolved relocations. This checks isolated functions, not complete
firmware, linked layout, or the identity of the original compiler.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'mcu/mainBoardGD/recovered/toolchain-probes.c'
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'
USER_CC = Path('/tmp/mainboardgd-atfe.fGpsbB/ATfE-22.1.0-Linux-x86_64/bin/clang')
FLAGS = ['--target=arm-none-eabi', '-mcpu=cortex-m7', '-mfpu=fpv5-d16',
         '-mfloat-abi=hard', '-O2', '-ffunction-sections', '-fdata-sections',
         '-Wall', '-Wextra', '-Werror']
CASES = [
    ('timer_is_before', 0x5518, 0x4418 + 0x5518, 6),
    ('timer_read_time', 0x5580, 0x4418 + 0x5580, 12),
    ('set_hold_current', 0x08001178, 0x1178, 56),
    ('set_run_current', 0x08001220, 0x1220, 52),
]


def compiler_path(requested):
    if requested:
        candidate = shutil.which(requested)
        if candidate is None:
            raise ValueError('compiler is not executable: ' + requested)
        return Path(candidate).resolve()
    candidates = sorted((ROOT / 'work/atfe').glob('**/bin/clang'))
    candidates.append(USER_CC)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError('no compiler found; pass --cc /path/to/clang or set MCU_GD_CC')


def code_sections(blob):
    """Read bounded ELF32 little-endian ARM sections and relocation targets."""
    if len(blob) < 52 or blob[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('expected ELF32 little-endian object')
    if struct.unpack_from('<HH', blob, 16) != (1, 40):
        raise ValueError('expected relocatable ARM object')
    offset = struct.unpack_from('<I', blob, 32)[0]
    entry_size, count, string_index = struct.unpack_from('<3H', blob, 46)
    if (entry_size != 40 or not count or string_index >= count
            or offset + count * entry_size > len(blob)):
        raise ValueError('invalid ELF section table')
    headers = [struct.unpack_from('<10I', blob, offset + i * entry_size)
               for i in range(count)]

    def contents(header):
        if header[4] + header[5] > len(blob):
            raise ValueError('truncated ELF section')
        return blob[header[4]:header[4] + header[5]]

    strings = contents(headers[string_index])
    sections = {}
    relocated = {header[7] for header in headers
                 if header[1] in (4, 9) and header[5]}
    for index, header in enumerate(headers):
        if header[0] >= len(strings):
            raise ValueError('invalid ELF section name offset')
        end = strings.find(b'\0', header[0])
        if end < 0:
            raise ValueError('unterminated ELF section name')
        name = strings[header[0]:end].decode('ascii')
        if name.startswith('.text.'):
            if index in relocated:
                raise ValueError('unresolved relocation in ' + name)
            if name in sections:
                raise ValueError('duplicate code section: ' + name)
            sections[name] = contents(header)
    return sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('MCU_GD_CC'))
    parser.add_argument('--cflag', action='append', default=[],
                        help='additional candidate GLOBAL compiler option')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'work/mainBoardGD-toolchain.json')
    parser.add_argument('--build-dir', type=Path,
                        default=ROOT / 'work/mainBoardGD-toolchain-probes')
    args = parser.parse_args()
    try:
        cc = compiler_path(args.cc)
        stock = STOCK.read_bytes()
        if hashlib.md5(stock).hexdigest() != STOCK_MD5:
            raise ValueError('unsupported stock image: address profile requires ' + STOCK_MD5)
        version = subprocess.run([str(cc), '--version'], check=True,
                                 capture_output=True, text=True).stdout.strip()
        args.build_dir.mkdir(parents=True, exist_ok=True)
        obj = args.build_dir.resolve() / 'toolchain-probes.o'
        command = [str(cc), *FLAGS, *args.cflag, '-c', str(SOURCE), '-o', str(obj)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        sections = code_sections(obj.read_bytes())
        results = []
        for name, address, file_offset, size in CASES:
            candidate = sections.get('.text.' + name)
            if candidate is None:
                raise ValueError('missing probe section: ' + name)
            expected = stock[file_offset:file_offset + size]
            exact = candidate == expected
            matched = sum(a == b for a, b in zip(candidate, expected))
            results.append({'name': name, 'stock_address': address,
                            'stock_file_offset': file_offset, 'stock_size': size,
                            'candidate_size': len(candidate), 'matched_bytes': matched,
                            'exact': exact, 'candidate_hex': candidate.hex(),
                            'stock_hex': expected.hex()})
            print('%-20s stock=%#010x %d/%d bytes %s (including literals)' %
                  (name, address, matched, size, 'EXACT' if exact else 'DIFF'))
        passed = all(result['exact'] for result in results)
        report = {'scope': 'isolated source probes, not whole firmware or linked layout',
                  'compiler': str(cc), 'compiler_version': version,
                  'compiler_sha256': hashlib.sha256(cc.read_bytes()).hexdigest(),
                  'compiler_checksum_provenance': 'local measurement; no public checksum comparison',
                  'source': str(SOURCE.relative_to(ROOT)),
                  'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  'stock_md5': STOCK_MD5, 'command': command, 'results': results,
                  'summary': {'passed': passed, 'functions': len(results),
                              'exact_functions': sum(r['exact'] for r in results),
                              'stock_bytes': sum(r['stock_size'] for r in results),
                              'matched_bytes': sum(r['matched_bytes'] for r in results)}}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n')
        print('%s: %d isolated functions, %d/%d bytes. JSON: %s' %
              ('PASS' if passed else 'FAIL', len(results),
               report['summary']['matched_bytes'], report['summary']['stock_bytes'], args.out))
        return 0 if passed else 1
    except (OSError, ValueError, struct.error, subprocess.CalledProcessError) as error:
        detail = getattr(error, 'stderr', None)
        parser.exit(1, str(error) + ('\n' + detail if detail else '') + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
