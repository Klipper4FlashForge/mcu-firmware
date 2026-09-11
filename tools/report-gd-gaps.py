#!/usr/bin/env python3
"""Classify inventory gaps without counting them as missing C functions.

Stock is comparison/read-only evidence. Known vectors and generic veneers are
verified against the actual partial ELF, scatter records against their separate
source-built artifact. Small zero spans are alignment inferences, not proofs of
the original linker script or newly recovered data objects.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_path(value):
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def split_range(start, end, spans):
    boundaries = {start, end}
    for left, right, _ in spans:
        if left < end and start < right:
            boundaries.update((max(start, left), min(end, right)))
    points = sorted(boundaries)
    return [(left, right, [meta for a, b, meta in spans if a <= left and right <= b])
            for left, right in zip(points, points[1:])]


def self_test():
    segments = split_range(10, 25, [(12, 20, 'body'), (20, 24, 'pool')])
    assert segments == [(10, 12, []), (12, 20, ['body']), (20, 24, ['pool']), (24, 25, [])]
    assert sum(b - a for a, b, _ in segments) == 15
    assert split_range(1, 2, []) == [(1, 2, [])]
    assert split_range(1, 2, [(0, 3, 'a'), (1, 2, 'b')]) == [(1, 2, ['a', 'b'])]
    print('gap partition boundary, overlap and extent self-tests passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=ROOT / 'work/mainBoardGD-progress.json')
    parser.add_argument('--partial-report', type=Path, default=ROOT / 'work/mainBoardGD-partial/results.json')
    parser.add_argument('--scatter-report', type=Path, default=ROOT / 'work/mainBoardGD-scatter/results.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-gaps.json')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    inventory = json.loads(args.inventory.read_text())
    stock_path = read_path(inventory['stock']['path'])
    stock = stock_path.read_bytes()
    if sha(stock) != inventory['stock']['sha256']:
        raise ValueError('inventory stock identity is stale')
    spec = importlib.util.spec_from_file_location('gd_layout', ROOT / 'tools/extract-gd-layout.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    layout = module.extract(stock)
    itcm = next(r for r in layout['regions'] if r['destination'] == 0)

    def stock_bytes(address, size):
        offset = address - 0x08000000 if address >= 0x08000000 else itcm['source'] - 0x08000000 + address
        data = stock[offset:offset + size]
        if len(data) != size:
            raise ValueError('stock range outside image')
        return data

    partial = json.loads(args.partial_report.read_text())
    elf_path = read_path(partial['linked_elf'])
    if sha(elf_path.read_bytes()) != partial['linked_elf_sha256']:
        raise ValueError('partial ELF hash differs from its report')
    structures = []
    with elf_path.open('rb') as stream:
        elf = ELFFile(stream)
        for row in partial['results']:
            if row['kind'] not in ('vectors', 'linker_veneer'):
                continue
            section = elf.get_section_by_name(row['output_section'])
            actual = section.data()
            expected = stock_bytes(row['address'], row['size'])
            if not (row['exact'] and section['sh_addr'] == row['address']
                    and len(actual) == row['size'] and actual == expected
                    and sha(actual) == row['actual_sha256']):
                raise ValueError('structural section mismatch: ' + row['name'])
            structures.append((row['address'], row['address'] + row['size'],
                               dict(kind='verified_' + row['kind'], name=row['name'],
                                    evidence='actual partial ELF versus stock')))
    # Independently require every extracted veneer and the complete vector extent.
    required = {(b['address'], b['address'] + b['size']) for b in layout['veneers']}
    required.add((0x08000000, layout['vector_end']))
    if {(a, b) for a, b, _ in structures} != required:
        raise ValueError('partial structural coverage differs from extracted layout')
    scatter = json.loads(args.scatter_report.read_text())
    payload = read_path(scatter['output']).read_bytes()
    if not (scatter['exact'] and sha(payload) == scatter['actual_sha256']
            and payload == stock_bytes(scatter['address'], scatter['size'])):
        raise ValueError('source-built scatter artifact differs from stock/report')
    structures.append((layout['region_table'], layout['region_table'] + 48,
                       dict(kind='verified_scatter_records', name='three scatter records',
                            evidence='source-built scatter artifact and dispatcher literals 080004e4/04e8')))
    records = inventory['records']
    regions = {}
    for name in ('itcm', 'flash'):
        region = inventory['regions'][name]
        gaps = region['partitions']['gaps_without_source_check']
        rows = []
        for gap in gaps['intervals']:
            for left, right, matches in split_range(gap['start'], gap['end'], structures):
                data = stock_bytes(left, right - left)
                if len(matches) > 1:
                    raise ValueError('overlapping structural classifications')
                classification = matches[0] if matches else dict(
                    kind='zero_alignment_candidate' if not any(data) else 'unclassified_nonzero',
                    evidence='observed bytes; no source object or original linker directive inferred')
                rows.append(dict(start=left, end=right, size=right - left,
                                 sha256=sha(data), **classification,
                                 end_alignment=(8 if right % 8 == 0 else 4 if right % 4 == 0 else 2 if right % 2 == 0 else 1),
                                 preceding_evidence=[dict(name=r['name'], gate=r['gate'], kind=r['kind'])
                                                     for r in records if r['address'] + r['size'] == left],
                                 following_evidence=[dict(name=r['name'], gate=r['gate'], kind=r['kind'])
                                                    for r in records if r['address'] == right]))
        counts = Counter()
        for row in rows:
            counts[row['kind']] += row['size']
        assert sum(counts.values()) == gaps['bytes']
        regions[name] = dict(inventory_gap_bytes=gaps['bytes'], categories=dict(counts), ranges=rows)
    # Address zero is a valid target. Tests must not treat it as a null vector.
    targets = {b['target'] for b in layout['veneers']}
    targets.update(v['target'] for v in layout['vectors'] if v['target'] is not None)
    target_rows = []
    for target in sorted(targets):
        owners = [r for r in records if r['address'] <= target < r['address'] + r['size']
                  and ('function' in r['kind'] or 'assembly' in r['kind'])]
        target_rows.append(dict(address=target, source_covered=bool(owners),
                                owners=[dict(name=r['name'], gate=r['gate'], status=r['status']) for r in owners]))
    result = dict(scope='read-only gap classification, not whole-image equality or new C coverage',
                  stock_sha256=sha(stock), inventory_sha256=sha(args.inventory.read_bytes()),
                  partial_report_sha256=sha(args.partial_report.read_bytes()),
                  partial_elf_sha256=sha(elf_path.read_bytes()),
                  scatter_report_sha256=sha(args.scatter_report.read_bytes()),
                  checker_sha256=sha(Path(__file__).read_bytes()),
                  inventory_stale_gates=inventory['summary'].get('stale_gates', []),
                  regions=regions, vector_and_veneer_targets=target_rows,
                  uncovered_entry_targets=[r['address'] for r in target_rows if not r['source_covered']],
                  limitations=['Coverage is the saved inventory snapshot, not a fresh compiler run.',
                               'Small zero gaps suggest alignment but do not prove absence of zero-valued objects.',
                               'Nonzero absence does not prove every current function boundary or semantic reconstruction correct.',
                               'Source-covered unmatched functions and standalone exclusions are not missing gap bytes.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    for name, region in regions.items():
        print(name, region['inventory_gap_bytes'], 'gap bytes:', region['categories'])
    print('Uncovered known vector/veneer targets:', result['uncovered_entry_targets'])
    print('Report:', args.out)
    return int(any(r['categories'].get('unclassified_nonzero', 0) for r in regions.values())
               or bool(result['uncovered_entry_targets']))


if __name__ == '__main__':
    raise SystemExit(main())
