#!/usr/bin/env python3
"""Build mainBoardGD scatter metadata and compressed RAM from the partial ELF.

This emits only flash 0x08003744..0x08004418, NOT a flashable firmware image.
RAM bytes come from compiled candidate sections. Stock is comparison input,
never an encoder input or source of candidate token choices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile
from gd_scatter_compress import CANONICAL_HYPOTHESIS, compress
from scatterload import decompress

ROOT = Path(__file__).resolve().parents[1]
FLASH, TABLE = 0x08000000, 0x08003744
RAM_START, RAM_SIZE = 0x24000000, 11912
ITCM_SIZE, ZERO_SIZE = 28120, 33976


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(ram):
    """Generic compression plus the recovered three-region layout policy."""
    if len(ram) != RAM_SIZE:
        raise ValueError('unexpected initialized RAM extent')
    compressed = compress(ram, CANONICAL_HYPOTHESIS)
    restored, consumed = decompress(compressed, RAM_SIZE)
    if restored != ram or consumed != len(compressed):
        raise ValueError('compressor round-trip failed')
    data_source = (TABLE + 3 * 16 + 7) & ~7
    itcm_source = (data_source + len(compressed) + 7) & ~7
    # These are semantic scatter records, not runtime instruction payloads.
    # Helpers remain explicitly unrecovered executable dependencies.
    records = [(data_source, RAM_START, RAM_SIZE, 0x080004ec),
               (itcm_source, 0, ITCM_SIZE, 0x0800335a),
               (itcm_source, RAM_START + RAM_SIZE, ZERO_SIZE, 0x0800336a)]
    table = b''.join(struct.pack('<4I', *record) for record in records)
    before = bytes(data_source - TABLE - len(table))
    after = bytes(itcm_source - data_source - len(compressed))
    return table + before + compressed + after, dict(
        records=[dict(source=s, destination=d, size=n, helper=h)
                 for s, d, n, h in records],
        compressed_size=len(compressed), compressed_sha256=sha(compressed),
        table_alignment_size=len(before), payload_alignment_size=len(after),
        compressed_source=data_source, itcm_source=itcm_source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--partial', type=Path, default=ROOT / 'work/mainBoardGD-partial/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-scatter')
    args = parser.parse_args()
    if args.self_test:
        for ram in (bytes(RAM_SIZE), bytes(i % 251 for i in range(RAM_SIZE))):
            result, layout = build(ram)
            assert len(result) == layout['itcm_source'] - TABLE
            assert layout['compressed_source'] % 8 == layout['itcm_source'] % 8 == 0
            for i, record in enumerate(layout['records']):
                assert struct.unpack_from('<4I', result, i * 16) == tuple(
                    record[key] for key in ('source', 'destination', 'size', 'helper'))
            offset = layout['compressed_source'] - TABLE
            restored, used = decompress(result[offset:], RAM_SIZE)
            assert restored == ram and used == layout['compressed_size']
            assert not any(result[48:offset])
            assert not any(result[offset + used:])
        for invalid in (b'', bytes(RAM_SIZE - 1), bytes(RAM_SIZE + 1)):
            try:
                build(invalid)
            except ValueError:
                pass
            else:
                raise AssertionError('accepted invalid RAM size')
        print('PASS: synthetic RAM compression, typed records, dynamic alignment and size rejection')
        return 0
    partial = json.loads(args.partial.read_text())
    for source, expected in partial['source_sha256'].items():
        path = Path(source)
        if not path.is_absolute():
            path = ROOT / path
        if sha(path.read_bytes()) != expected:
            raise ValueError('partial build source changed: ' + source)
    elf_path = Path(partial['linked_elf'])
    ram, coverage = bytearray(RAM_SIZE), bytearray(RAM_SIZE)
    with elf_path.open('rb') as stream:
        elf = ELFFile(stream)
        for row in partial['results']:
            if not RAM_START <= row['address'] < RAM_START + RAM_SIZE:
                continue
            section = elf.get_section_by_name(row['output_section'])
            if section is None or section['sh_addr'] != row['address']:
                raise ValueError('missing or moved candidate RAM section')
            data = section.data()
            offset = row['address'] - RAM_START
            if (len(data) != row['size'] or offset + len(data) > RAM_SIZE
                    or any(coverage[offset:offset + len(data)])):
                raise ValueError('overlap or incorrect candidate RAM section size')
            if sha(data) != row['actual_sha256']:
                raise ValueError('candidate RAM section differs from partial report')
            ram[offset:offset + len(data)] = data
            coverage[offset:offset + len(data)] = bytes([1]) * len(data)
    if not all(coverage):
        raise ValueError('candidate initialized RAM has uncovered bytes')
    candidate, layout = build(bytes(ram))
    stock_path = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
    stock = stock_path.read_bytes()
    if hashlib.md5(stock).hexdigest() != 'fb64911bac422a27d7ed7fab3597603f':
        raise ValueError('unexpected comparison image')
    expected = stock[TABLE - FLASH:0x4418]
    exact = candidate == expected
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out / 'scatter-data.bin'
    output.write_bytes(candidate)
    report = dict(scope='scatter records, alignment and compressed initialized RAM only; NOT firmware',
                  whole_image_verified=False, address=TABLE, size=len(expected),
                  actual_size=len(candidate), exact=exact,
                  matching_bytes=sum(a == b for a, b in zip(candidate, expected)),
                  expected_sha256=sha(expected), actual_sha256=sha(candidate),
                  output=str(output.resolve()), input_elf=str(elf_path),
                  input_elf_sha256=sha(elf_path.read_bytes()), input_ram_sha256=sha(ram),
                  partial_report=str(args.partial.resolve()),
                  partial_report_sha256=sha(args.partial.read_bytes()),
                  source_sha256={str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in
                                 [Path(__file__).resolve(), ROOT / 'tools/gd_scatter_compress.py',
                                  ROOT / 'tools/scatterload.py']},
                  encoder=CANONICAL_HYPOTHESIS, layout=layout)
    (args.out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Source-built scatter/data span: {len(candidate)}/{len(expected)} bytes, '
          + ('EXACT' if exact else 'DIFF'))
    print(f'Compressed payload {layout["compressed_size"]} bytes; '
          f'ITCM load source {layout["itcm_source"]:#010x}')
    print('Runtime helpers and ITCM payload are not supplied by this artifact.')
    return int(not exact)


if __name__ == '__main__':
    raise SystemExit(main())
