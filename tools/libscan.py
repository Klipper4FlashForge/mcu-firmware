#!/usr/bin/env python3
"""Find which C library an image's runtime helpers came from.

`objalign.py` settles a GCC toolchain by matching `__udivmoddi4` out of a
candidate libgcc.  The same argument works against Arm's C libraries, and
it is the only way left to pin the compiler for an image -- like
mainBoardGD's -- that GCC did not build: a handful of routines in the
image are library code, so they must appear byte-for-byte in the library
the linker pulled them from.

    libscan.py <image.bin> <lib-dir> [<lib-dir> ...]

Each `<lib-dir>` is a directory of Arm library archives (`armlib`,
`microlib`, `cpplib` -- `*.l` and `*.b`).  Report is one line per routine
per directory; a miss excludes that whole library, which is the point.

Archives and objects are read directly rather than shelled out to
`ar`/`objcopy`: Arm names its code sections `!!!scatter`, `!!handler_copy`,
`!!dclz77c`, and `objcopy -O binary -j` silently writes an empty file for
those, which turns every comparison into a false negative.

The routines and their offsets are mainBoardGD's; edit ROUTINES for
another image.
"""
import argparse
import glob
import os
import struct
import sys

# name -> (offset in image, length).  Boundaries read off the disassembly.
ROUTINES = {
    'strcmp':                 (0x458, 0x1c),
    'setjmp':                 (0x488, 0x1a),
    'longjmp':                (0x4a2, 0x24),
    '__scatterload':          (0x4c8, 0x1c),
    '__decompress':           (0x4ec, 0x5e),
    '__scatterload_copy':     (0x335a, 0x0e),
    '__scatterload_zeroinit': (0x336a, 0x0e),
}

SHT_PROGBITS = 1
SHF_EXECINSTR = 0x4


def ar_members(data):
    """Yield (name, bytes) for each member of a Unix `ar` archive."""
    if not data.startswith(b'!<arch>\n'):
        return
    pos, longnames = 8, b''
    while pos + 60 <= len(data):
        header = data[pos:pos + 60]
        name = header[0:16].decode('latin1').rstrip()
        try:
            size = int(header[48:58].decode('latin1').strip())
        except ValueError:
            return
        body = data[pos + 60:pos + 60 + size]
        pos += 60 + size + (size & 1)
        if name.startswith('//'):
            longnames = body                      # GNU long-name table
            continue
        if name.startswith('/') and name[1:].isdigit():
            off = int(name[1:])
            end = longnames.find(b'/\n', off)
            name = longnames[off:end].decode('latin1')
        name = name.rstrip('/')
        if name and not name.startswith('/'):
            yield name, body


def code_sections(obj):
    """Yield the bytes of every executable PROGBITS section of an ELF32."""
    if len(obj) < 52 or obj[:4] != b'\x7fELF' or obj[4] != 1:
        return
    little = obj[5] == 1
    end = '<' if little else '>'
    shoff, = struct.unpack_from(end + 'I', obj, 32)
    shentsize, shnum = struct.unpack_from(end + 'HH', obj, 46)
    for i in range(shnum):
        base = shoff + i * shentsize
        if base + 40 > len(obj):
            return
        _, stype, flags, _, offset, size = struct.unpack_from(
            end + 'IIIIII', obj, base)
        if stype == SHT_PROGBITS and flags & SHF_EXECINSTR and size:
            yield obj[offset:offset + size]


def scan(libdir, targets):
    hits = {}
    archives = sorted(glob.glob(libdir + '/*.l')) + sorted(glob.glob(libdir + '/*.b'))
    for archive in archives:
        data = open(archive, 'rb').read()
        for member, obj in ar_members(data):
            for body in code_sections(obj):
                for name, want in targets.items():
                    if body[:len(want)] == want:
                        hits.setdefault(name, set()).add(
                            (os.path.basename(archive), member))
    return len(archives), hits


def main():
    p = argparse.ArgumentParser()
    p.add_argument('image')
    p.add_argument('libdir', nargs='+')
    p.add_argument('--self-test', action='store_true',
                   help="take the targets from the first lib-dir's own "
                        "scatter helpers, which must then match themselves")
    args = p.parse_args()
    data = open(args.image, 'rb').read()
    targets = {n: data[off:off + size] for n, (off, size) in ROUTINES.items()}

    if args.self_test:
        targets = {}
        for archive in sorted(glob.glob(args.libdir[0] + '/*.l'))[:1]:
            for member, obj in ar_members(open(archive, 'rb').read()):
                if member in ('__scatter_copy.o', '__dclz77c.o'):
                    for body in code_sections(obj):
                        targets['self:' + member] = body
        if not targets:
            sys.exit("self-test: no scatter helpers in %s" % args.libdir[0])

    for libdir in args.libdir:
        n, hits = scan(libdir, targets)
        print("=== %s  (%d archives)" % (libdir, n))
        for name in targets:
            found = hits.get(name, set())
            print("   %-24s %s" % (name, ', '.join(
                '%s:%s' % x for x in sorted(found)[:4]) if found else '-'))


if __name__ == '__main__':
    main()
