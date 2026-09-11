#!/usr/bin/env python3
"""Which compiler family built an image, from two habits it cannot hide.

A 32-bit constant is either loaded from a literal pool or built with a
`movw`/`movt` pair, and the choice is a compiler default, not a source
property: GCC and armcc pool, LLVM (and so armclang) pairs.  And LLVM
keeps r7 as the frame register, so its prologues push r7 where GCC's push
r3 or r4.  Counting both over a whole image separates an LLVM-derived
toolchain from a GCC one without a single byte having to match.

    codegen-style.py <image.bin> <load-addr> [<image.bin> <load-addr> ...]

Run it against a board whose toolchain is known -- the levelBoard is
GCC 10.3 -- alongside the one in question, and read the ratio.
"""
import re
import subprocess
import sys

PATTERNS = [
    ('movw', re.compile(r'\bmovw\b')),
    ('ldr rN,[pc', re.compile(r'ldr\s+r[0-9]+, \[pc')),
    ('push {r7,..', re.compile(r'push\s+\{r7,')),
    ('adr', re.compile(r'add\s+r[0-9]+, pc')),
]


def counts(path, load):
    out = subprocess.run(
        ['arm-none-eabi-objdump', '-D', '-b', 'binary', '-m', 'arm',
         '-M', 'force-thumb', '--adjust-vma=%#x' % load, path],
        capture_output=True, text=True, check=True).stdout
    return [sum(1 for l in out.splitlines() if p.search(l)) for _, p in PATTERNS]


def main():
    args = sys.argv[1:]
    if not args or len(args) % 2:
        sys.exit(__doc__)
    print("%-28s %s" % ('image', ' '.join('%10s' % n for n, _ in PATTERNS)))
    for i in range(0, len(args), 2):
        path, load = args[i], int(args[i + 1], 0)
        print("%-28s %s" % (path.split('/')[-1],
                            ' '.join('%10d' % c for c in counts(path, load))))


if __name__ == '__main__':
    main()
