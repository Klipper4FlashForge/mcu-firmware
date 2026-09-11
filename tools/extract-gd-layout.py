#!/usr/bin/env python3
"""Recover mainBoardGD vectors and cross-region branch veneers.

    python3 tools/extract-gd-layout.py mcu/mainBoardGD/stock/mainBoardGD.bin

JSON goes to stdout. Addresses are execution addresses, not file offsets.
This is a map of the supplied stock image, not a reconstructed linker script.
The anchors apply to the 45,552-byte mainBoardGD image documented in
mcu/mainBoardGD/notes/recon.md. No compiler or Ghidra export is required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scatterload import HELPERS, decompress, entries


FLASH = 0x08000000
TABLE = 0x08003744
VECTOR_END = 0x080003A4
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'
CORE = {
    1: 'Reset', 2: 'NMI', 3: 'HardFault', 4: 'MemManage',
    5: 'BusFault', 6: 'UsageFault', 11: 'SVCall', 12: 'DebugMon',
    14: 'PendSV', 15: 'SysTick',
}


def wide_immediate(first, second):
    return ((first & 15) << 12 | ((first >> 10) & 1) << 11
            | ((second >> 12) & 7) << 8 | second & 255)


def veneers(blob, base):
    """Exact Thumb encoding: movw ip, #lo; movt ip, #hi; bx ip."""
    result = []
    for offset in range(0, len(blob) - 9, 2):
        low1, low2, high1, high2, branch = struct.unpack_from('<5H', blob, offset)
        if ((low1 & 0xFBF0) != 0xF240 or (high1 & 0xFBF0) != 0xF2C0
                or (low2 & 0x8F00) != 0x0C00 or (high2 & 0x8F00) != 0x0C00
                or branch != 0x4760):
            continue
        pointer = wide_immediate(low1, low2) | wide_immediate(high1, high2) << 16
        if not pointer & 1:
            raise ValueError('veneer destination is not Thumb at %#x' % (base + offset))
        result.append({'address': base + offset, 'target': pointer & ~1,
                       'thumb_pointer': pointer, 'size': 10})
    return result


def extract(data):
    digest = hashlib.md5(data).hexdigest()
    if digest != STOCK_MD5:
        raise ValueError('unsupported image: anchors require mainBoardGD MD5 ' + STOCK_MD5)
    regions = []
    itcm = None
    for src, dst, size, fn in entries(data, FLASH, TABLE - FLASH):
        kind = HELPERS.get(data[fn - FLASH:fn - FLASH + 8])
        region = {'source': src, 'destination': dst, 'size': size,
                  'helper': fn, 'kind': kind}
        if kind == 'copy':
            blob = data[src - FLASH:src - FLASH + size]
            if len(blob) != size:
                raise ValueError('truncated copy region')
            if dst == 0:
                itcm = blob
        elif kind == 'decompress':
            blob, used = decompress(data[src - FLASH:], size)
            if len(blob) != size:
                raise ValueError('decompressed size mismatch')
            region['compressed_size'] = used
        elif kind != 'zeroinit':
            raise ValueError('unknown scatterload helper')
        regions.append(region)
    if itcm is None or len(regions) != 3:
        raise ValueError('expected ITCM and three scatterload regions')

    bridges = veneers(data[:TABLE - FLASH], FLASH) + veneers(itcm, 0)
    for bridge in bridges:
        target = bridge['target']
        source_in_flash = bridge['address'] >= FLASH
        target_in_flash = FLASH <= target < TABLE
        target_in_itcm = 0 <= target < len(itcm)
        if not (target_in_itcm if source_in_flash else target_in_flash):
            raise ValueError('veneer does not cross code regions: %r' % bridge)
        bridge['direction'] = 'flash_to_itcm' if source_in_flash else 'itcm_to_flash'
    vectors = []
    for slot in range(1, (VECTOR_END - FLASH) // 4):
        pointer = struct.unpack_from('<I', data, slot * 4)[0]
        target = pointer & ~1
        if pointer and (not pointer & 1 or not
                        (target < len(itcm) or FLASH <= target < TABLE)):
            raise ValueError('invalid vector at slot %d' % slot)
        vectors.append({'slot': slot, 'irq': slot - 16 if slot >= 16 else None,
                        'name': CORE.get(slot, 'IRQ%d' % (slot - 16)
                                         if slot >= 16 else 'reserved'),
                        'pointer': pointer, 'target': pointer & ~1 if pointer else None,
                        'default_handler': pointer == 0x080003E5})
    return {'stock_md5': digest, 'image_size': len(data), 'region_table': TABLE,
            'initial_sp': struct.unpack_from('<I', data)[0],
            'vector_end': VECTOR_END, 'regions': regions, 'vectors': vectors,
            'veneers': bridges,
            'summary': {'vector_slots_including_sp': len(vectors) + 1,
                        'active_vectors': sum(v['pointer'] != 0 and not v['default_handler']
                                              for v in vectors),
                        'default_vectors': sum(v['default_handler'] for v in vectors),
                        'reserved_vectors': sum(v['pointer'] == 0 for v in vectors),
                        'flash_to_itcm_veneers': sum(v['direction'] == 'flash_to_itcm'
                                                     for v in bridges),
                        'itcm_to_flash_veneers': sum(v['direction'] == 'itcm_to_flash'
                                                     for v in bridges)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('--out', type=Path, help='write JSON here instead of stdout')
    args = parser.parse_args()
    try:
        with open(args.image, 'rb') as stream:
            result = extract(stream.read())
        output = json.dumps(result, indent=2) + '\n'
        if args.out:
            args.out.write_text(output)
        else:
            print(output, end='')
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
