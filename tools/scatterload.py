#!/usr/bin/env python3
"""Unpack an ARM-Compiler-linked image: Region$$Table, LZ77, load regions.

An image linked by armlink (Keil MDK / ARM Compiler) carries a table of
{src, dst, size, fn} quadruples -- ``Region$$Table`` -- that ``__scatterload``
walks at boot, calling ``fn`` on each entry to copy, zero-fill, or decompress
the region into RAM.  The mainBoardGD image is built this way, which is why a
naive load at 0x08000000 disassembles into garbage past the first 17 KB: most
of its code runs from ITCM at address 0, and its ``.data`` is LZ77-compressed.

    scatterload.py <image.bin> <load-addr> [--table ADDR] [--out DIR]

With ``--out`` each region is written to ``<DIR>/<dst>.bin`` -- the ITCM image
and the expanded ``.data`` become ordinary files to disassemble and grep.
"""
import argparse
import struct
import sys

# The three helpers are ARM C library code and byte-stable across versions.
HELPERS = {
    b'\x02\xe0\x08\xc8\x12\x1f\x08\xc1': 'copy',
    b'\x00\x20\x01\xe0\x01\xc1\x12\x1f': 'zeroinit',
    b'\x70\xb5\x8d\x18\x10\xf8\x01\x4b': 'decompress',
}


def decompress(src, out_size):
    """armlink's __decompress.  Each token byte carries a literal count in
    bits 0-1 (0 => the count is the next byte, and it is one more than the
    number of literals) and a match length in bits 4-7 (0 => the next byte).
    A match's distance is the following byte plus bits 2-3 scaled by 64, or,
    when those bits are all set, plus a second byte scaled by 256."""
    i = 0
    dst = bytearray()
    while len(dst) < out_size:
        token = src[i]; i += 1
        nlit = token & 3
        if nlit == 0:
            nlit = src[i]; i += 1
        mlen = token >> 4
        if mlen == 0:
            mlen = src[i]; i += 1
        for _ in range(nlit - 1):
            dst.append(src[i]); i += 1
        if mlen:
            dist = src[i]; i += 1
            hi = token & 12
            dist += (src[i] << 8) if hi == 12 else (hi << 6)
            if hi == 12:
                i += 1
            pos = len(dst) - dist
            if pos < 0:
                raise ValueError("match before start of output")
            for _ in range(mlen + 2):
                dst.append(dst[pos]); pos += 1
    return bytes(dst), i


def entries(data, load, off):
    """Yield table entries until one stops looking like a region: a
    destination inside flash, or a helper outside the image, ends the run."""
    while off + 16 <= len(data):
        src, dst, size, fn = struct.unpack('<4I', data[off:off + 16])
        if not size:  # the table ends with a zero-sized entry
            return
        if not load <= fn < load + len(data):
            return
        if load <= dst < load + len(data):     # regions land in RAM, not flash
            return
        yield src, dst, size, fn
        off += 16


def find_table(data, load):
    best = None
    for off in range(0, len(data) - 16, 4):
        n = sum(1 for _ in entries(data, load, off))
        if n >= 2 and (best is None or n > best[1]):
            best = (off, n)
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument('image')
    p.add_argument('load', type=lambda s: int(s, 0))
    p.add_argument('--table', type=lambda s: int(s, 0))
    p.add_argument('--out')
    args = p.parse_args()
    data = open(args.image, 'rb').read()

    off = (args.table - args.load if args.table is not None
           else (find_table(data, args.load) or (None,))[0])
    if off is None:
        sys.exit("no Region$$Table found -- is this an armlink image?")
    print("Region$$Table at %#010x" % (args.load + off))

    for src, dst, size, fn in entries(data, args.load, off):
        code = data[fn - args.load:fn - args.load + 8]
        kind = HELPERS.get(code, 'unknown')
        blob = None
        if kind == 'decompress':
            blob, used = decompress(data[src - args.load:], size)
            note = "decompress (%d compressed)" % used
        elif kind == 'copy':
            blob = data[src - args.load:src - args.load + size]
            note = "copy"
        else:
            note = kind
        print("  %#010x -> %#010x  %6d bytes  %s  fn=%#010x"
              % (src, dst, size, note, fn))
        if args.out and blob is not None:
            path = "%s/%08x.bin" % (args.out.rstrip('/'), dst)
            open(path, 'wb').write(blob)
            print("      written %s" % path)


if __name__ == '__main__':
    main()
