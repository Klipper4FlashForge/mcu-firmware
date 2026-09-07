#!/usr/bin/env python3
"""Build decomp-permuter's base.c for one function of our Klipper tree.

    mkbase.py <source file relative to the tree> <function> <outdir>

pycparser cannot parse GCC attributes where Klipper puts them, so the unit
is preprocessed with `__attribute__(x)` defined away, and the two attributes
that change code are put back in forms pycparser reproduces verbatim:

  * `noinline` functions get a prior prototype carrying the attribute (the
    body stays: GCC's IPA analysis of it shapes the callers);
  * a static variable in a named section is never constant-folded, while
    the same variable without the attribute would be, so those lose
    `static` instead.

Every other function body is kept: GCC -O2 inlines statics and globals
into the target and deletes stores to write-only statics.
"""
import os, re, subprocess, sys

ROOT = os.environ.get('MCU_ROOT', os.getcwd())
WORK = os.environ.get('MCU_WORK', os.path.join(ROOT, 'work'))
TREE = os.environ.get('MCU_TREE', os.path.join(ROOT, 'klipper'))
GCC = os.path.join(WORK, 'gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-gcc')
FLAGS = os.environ['MCU_CFLAGS'].split()  # newtarget.sh exports the tree's compile line

src, func, out = sys.argv[1:4]
def pp(extra):
    return subprocess.run([GCC] + FLAGS + ['-E', '-P'] + extra + [src],
                          capture_output=True, text=True, cwd=TREE, check=True).stdout
full = pp([])
base = pp(["-D__attribute__(x)="])

noinl = set(re.findall(r'noinline[^;{]*?\b(?!__)(\w+)\s*\(', full))
for v in re.findall(r'\bstatic\s+[^;=(){}]*?\b(\w+)\s+__attribute__\(\(section', full):
    base = re.sub(r'\bstatic\s+((?:const\s+|volatile\s+)*\w+\s+' + v + r'\b)', r'\1', base)
base = base.replace('__attribute__((__attribute__((noinline))))', '__attribute__((noinline))')

KW = {'if', 'while', 'for', 'switch', 'return', 'sizeof', 'else', 'do'}
def bracket_end(s, i):
    level = 0
    while i < len(s):
        if s[i] == '{': level += 1
        elif s[i] == '}':
            level -= 1
            if level == 0: return i
        i += 1
    raise SystemExit('unbalanced braces')
rx = re.compile(r'\b(\w+)\s*\((?:[^;{}()]|\([^;{}()]*\))*\)\s*\{')
outp = []; pos = 0
while True:
    m = rx.search(base, pos)
    if not m:
        outp.append(base[pos:]); break
    nm = m.group(1)
    if nm in KW or nm.startswith('PERM'):
        outp.append(base[pos:m.end()]); pos = m.end(); continue
    head_start = max(base.rfind(c, 0, m.start()) for c in ';}{') + 1
    end = bracket_end(base, m.end() - 1)
    if nm in noinl and nm != func:
        proto = base[head_start:m.end() - 1].strip()
        outp.append(base[pos:head_start] + proto + ' __attribute__((noinline));\n' + base[head_start:end + 1])
    else:
        outp.append(base[pos:end + 1])
    pos = end + 1
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'base.c'), 'w').write(''.join(outp))
print(f'{out}/base.c written ({len(noinl)} noinline: {sorted(noinl)})')
