#!/usr/bin/env python3
"""Assemble a whole mainBoardGD flash image from the partial ELF and score it.

Stock's flash image is three spans: the flash-resident code and data at
0x08000000..0x08003744, the scatter table with the compressed initialized RAM
at 0x08003744..0x08004418, and the ITCM payload (28,120 bytes copied to
address 0 at boot) at 0x08004418..0x0800B1F0. This tool paints every allocated
PROGBITS section of the partial ELF into those spans at its own address,
appends the source-built scatter span, and compares the result with stock
byte for byte. Bytes no section covers are left zero and reported separately
from bytes a recovered section gets wrong.

The output is a candidate image and the whole-image differing-byte count,
the same gate the levelBoard was driven by. It becomes firmware only when
that count is zero.
"""
import argparse
import bisect
import hashlib
import importlib.util
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
FLASH, TABLE, ITCM_SOURCE = 0x08000000, 0x08003744, 0x08004418
ITCM_SIZE = 28120
IMAGE_SIZE = ITCM_SOURCE - FLASH + ITCM_SIZE
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module(filename):
    spec = importlib.util.spec_from_file_location(filename.replace('-', '_'), ROOT / 'tools' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def image_offset(address):
    """Map a runtime address to its flash-image offset, or None if not in the image."""
    if FLASH <= address < ITCM_SOURCE:
        return address - FLASH
    if 0 <= address < ITCM_SIZE:
        return ITCM_SOURCE - FLASH + address
    return None


def runs(flags):
    """Contiguous [start, end) runs of set bytes in a byte mask."""
    start = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            yield start, i
            start = None
    if start is not None:
        yield start, len(flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, default=ROOT / 'work/mainBoardGD-partial/partial.elf')
    parser.add_argument('--scatter', type=Path, default=ROOT / 'work/mainBoardGD-scatter/scatter-data.bin')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-image')
    parser.add_argument('--limit', type=int, default=40, help='differing spans to print (0 = all)')
    args = parser.parse_args()

    stock = STOCK.read_bytes()
    if hashlib.md5(stock).hexdigest() != STOCK_MD5 or len(stock) != IMAGE_SIZE:
        raise ValueError('unexpected comparison image')

    image, owner = bytearray(IMAGE_SIZE), [None] * IMAGE_SIZE
    sections = []
    with args.elf.open('rb') as stream:
        elf = ELFFile(stream)
        for section in elf.iter_sections():
            if section['sh_type'] != 'SHT_PROGBITS' or not section['sh_flags'] & 0x2:
                continue
            offset, size = image_offset(section['sh_addr']), section['sh_size']
            if offset is None or size == 0:
                continue
            if offset + size > IMAGE_SIZE:
                raise ValueError(f'{section.name} runs past the image')
            if any(owner[offset:offset + size]):
                raise ValueError(f'{section.name} overlaps an already painted span')
            image[offset:offset + size] = section.data()
            owner[offset:offset + size] = [section.name] * size
            sections.append((offset, size, section.name))

    scatter = args.scatter.read_bytes()
    offset = TABLE - FLASH
    if len(scatter) != ITCM_SOURCE - TABLE:
        raise ValueError('scatter span has the wrong extent')
    if any(owner[offset:offset + len(scatter)]):
        raise ValueError('scatter span overlaps an ELF section')
    image[offset:offset + len(scatter)] = scatter
    owner[offset:offset + len(scatter)] = ['scatter-data'] * len(scatter)
    sections.append((offset, len(scatter), 'scatter-data'))
    sections.sort()

    differ = bytes(a != b for a, b in zip(image, stock))
    covered = bytes(o is not None for o in owner)
    uncovered = bytes(not c for c in covered)
    uncovered_nonzero = bytes(bool(u and s) for u, s in zip(uncovered, stock))

    per_section = []
    for offset, size, name in sections:
        bad = sum(differ[offset:offset + size])
        if bad:
            per_section.append(dict(section=name, address=address_of(offset), size=size,
                                    differing=bad))
    per_section.sort(key=lambda r: -r['differing'])

    gaps = []
    for start, end in runs(uncovered):
        nonzero = sum(uncovered_nonzero[start:end])
        gaps.append(dict(address=address_of(start), size=end - start, stock_nonzero_bytes=nonzero))

    total = sum(differ)
    in_covered = sum(d and c for d, c in zip(differ, covered))
    report = dict(
        scope='whole flash image assembled from the partial ELF and the source-built scatter span',
        whole_image_verified=total == 0,
        image_size=IMAGE_SIZE, differing_bytes=total,
        differing_in_recovered_sections=in_covered,
        differing_in_uncovered_gaps=total - in_covered,
        uncovered_bytes=sum(uncovered), uncovered_gaps=gaps,
        sections_with_differences=per_section,
        sections_painted=len(sections),
        candidate_sha256=sha(image), stock_sha256=sha(stock),
        input_elf=str(args.elf.resolve()), input_elf_sha256=sha(args.elf.read_bytes()),
        input_scatter=str(args.scatter.resolve()), input_scatter_sha256=sha(scatter))

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'mainBoardGD-candidate.bin').write_bytes(image)
    (args.out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    print(f'Whole image: {IMAGE_SIZE - total}/{IMAGE_SIZE} bytes match stock; '
          f'{total} differ ({in_covered} inside recovered sections, '
          f'{total - in_covered} in uncovered gaps)')
    print(f'Uncovered: {sum(uncovered)} bytes in {len(gaps)} gaps, '
          f'{sum(uncovered_nonzero)} of them nonzero in stock')
    for gap in gaps:
        if gap['stock_nonzero_bytes']:
            print(f"  gap {gap['address']:#010x} +{gap['size']:<5} {gap['stock_nonzero_bytes']} nonzero")
    shown = per_section if args.limit == 0 else per_section[:args.limit]
    print(f'{len(per_section)} recovered sections differ:')
    for row in shown:
        print(f"  {row['address']:#010x} {row['differing']:>4}/{row['size']:<5} {row['section']}")
    if len(shown) < len(per_section):
        print(f'  ... {len(per_section) - len(shown)} more')
    print(f"Candidate: {args.out / 'mainBoardGD-candidate.bin'}; "
          + ('WHOLE IMAGE EXACT' if total == 0 else 'whole-image equality NOT VERIFIED'))
    return int(total != 0)


def address_of(offset):
    if offset >= ITCM_SOURCE - FLASH:
        return offset - (ITCM_SOURCE - FLASH)
    return FLASH + offset


if __name__ == '__main__':
    raise SystemExit(main())
