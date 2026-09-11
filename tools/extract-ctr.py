#!/usr/bin/env python3
"""Recover Klipper's compile-time-request text from an image that kept it.

Klipper's DECL_* macros drop a NUL-terminated string into a
``.compile_time_request`` section; ``scripts/buildcommands.py`` reads those
strings back out of the object files to generate the command table and the
data dictionary.  Nothing references the strings, so a GNU link with
``--gc-sections`` drops them and the three STM32 boards' images carry none.
The mainBoardGD image was linked by a toolchain that kept them, so its whole
.ctr text -- every command, encoder, constant, enumeration, task and shutdown
function, in link order -- is sitting in its initialised data.

    extract-ctr.py <data-region.bin> [out.txt]

Feed it the expanded ``.data`` region (see ``scatterload.py --out``).
"""
import re
import sys

# Every request begins with DECL_ or _DECL_ and is plain text to its NUL.
ENTRY = re.compile(rb'_?DECL_[\x09\x20-\x7e]*')


def main():
    data = open(sys.argv[1], 'rb').read()
    out = sys.stdout if len(sys.argv) < 3 else open(sys.argv[2], 'w')
    n = 0
    for m in ENTRY.finditer(data):
        out.write("%08x %s\n" % (m.start(), m.group().decode()))
        n += 1
    if out is not sys.stdout:
        out.close()
    sys.stderr.write("%d requests\n" % n)


if __name__ == '__main__':
    main()
