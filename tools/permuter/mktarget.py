#!/usr/bin/env python3
"""Build decomp-permuter's target.o from a function in the stock image.

    mktarget.py <name> <stock-addr-hex> <size> <outdir>

Walks the stock bytes instruction by instruction (Thumb-2 width rule),
recognises the literal pool from pc-relative loads, emits code as
.inst.n/.inst.w, pool words that name a known symbol as `.word sym`, and
bl / b.w to other functions as symbolic branches, so the object looks like
compiler output and the permuter's scorer compares like with like.

Symbol names come from `relocmap.py --all --limit 0` (functions, at their
stock address) and from our own ELF for data whose address is unchanged;
pass MCU_RAMMAP=<file> with lines `0x<stock> 0x<ours> <name>` to name the
rest. Unnamed pool words stay numeric, which costs every candidate the same.
"""
import os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('MCU_ROOT', os.getcwd())
WORK = os.environ.get('MCU_WORK', os.path.join(ROOT, 'work'))
TREE = os.environ.get('MCU_TREE', os.path.join(ROOT, 'klipper'))
STOCK = os.environ.get('MCU_STOCK', os.path.join(ROOT, 'mcu/levelBoard/stock/levelBoard.bin'))
LOAD = 0x08004000
TOOLS = os.path.join(WORK, 'gcc-arm-none-eabi-10.3-2021.10/bin')

name, addr, size, out = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3]), sys.argv[4]
BIN = open(STOCK, 'rb').read()

sym = {}
nm = subprocess.run([os.path.join(TOOLS, 'arm-none-eabi-nm'), '-n',
                     os.path.join(TREE, 'out/klipper.elf')], capture_output=True, text=True).stdout
for l in nm.splitlines():
    a, t, n = l.split()
    if t in 'dDbBrRtT':
        sym.setdefault(int(a, 16), n)
env = dict(os.environ, MCU_TREE=TREE)
rm = subprocess.run(['python3', os.path.join(HERE, '..', 'relocmap.py'), '--all', '--limit', '0'],
                    capture_output=True, text=True, cwd=ROOT, env=env).stdout
for l in rm.splitlines():
    m = re.match(r'\s+\S+\s+(\S+)\s+ours=0x[0-9a-f]+ stock=0x([0-9a-f]+)', l)
    if m:
        sym[int(m.group(2), 16)] = m.group(1)
if os.environ.get('MCU_RAMMAP'):
    for l in open(os.environ['MCU_RAMMAP']):
        m = re.match(r'0x([0-9a-f]+)\s+0x[0-9a-f]+\s+(\S+)', l)
        if m:
            sym[int(m.group(1), 16)] = m.group(2)
sym[addr] = name

def hw(a): return struct.unpack_from('<H', BIN, a - LOAD)[0]
def wide(h): return (h >> 11) in (0b11101, 0b11110, 0b11111)

def bl_target(a, h1, h2):
    s = (h1 >> 10) & 1; imm10 = h1 & 0x3ff
    j1 = (h2 >> 13) & 1; j2 = (h2 >> 11) & 1; imm11 = h2 & 0x7ff
    i1 = ~(j1 ^ s) & 1; i2 = ~(j2 ^ s) & 1
    imm = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s: imm -= 1 << 25
    return a + 4 + imm

# pass 1: literal pool = targets of ldr Rt,[pc,#imm], ldr.w and vldr
pool = set(); a = addr; end = addr + size
while a < end:
    if a in pool: a += 4; continue
    h1 = hw(a)
    if wide(h1):
        h2 = hw(a + 2)
        if (h1 & 0xff7f) == 0xf85f:
            imm = h2 & 0xfff; pool.add(((a + 4) & ~3) + (imm if h1 & 0x80 else -imm))
        if (h1 & 0xff3f) == 0xed1f:
            imm = (h2 & 0xff) * 4; pool.add(((a + 4) & ~3) + (imm if h1 & 0x80 else -imm))
        a += 4
    else:
        if (h1 >> 11) == 0b01001:
            pool.add(((a + 4) & ~3) + (h1 & 0xff) * 4)
        a += 2
# pass 2: emit
lines = []; a = addr
while a < end:
    if a in pool:
        v = struct.unpack_from('<I', BIN, a - LOAD)[0]
        tgt = sym.get(v) or (sym.get(v & ~1) if v & 1 else None)
        lines.append(f'\t.word {tgt}' if tgt else f'\t.word 0x{v:08x}'); a += 4; continue
    h1 = hw(a)
    if wide(h1):
        h2 = hw(a + 2); mn = None
        if (h1 & 0xf800) == 0xf000 and (h2 & 0xd000) == 0xd000: mn = 'bl'
        elif (h1 & 0xf800) == 0xf000 and (h2 & 0xd000) == 0x9000: mn = 'b.w'
        if mn:
            tv = bl_target(a, h1, h2)
            if mn == 'bl' or not (addr <= tv < end):
                tgt = sym.get(tv)
                if tgt: lines.append(f'\t{mn} {tgt}'); a += 4; continue
                print(f'warning: no symbol for {mn} {tv:08x} at {a:08x}', file=sys.stderr)
        lines.append(f'\t.inst.w 0x{h1:04x}{h2:04x}'); a += 4
    else:
        lines.append(f'\t.inst.n 0x{h1:04x}'); a += 2
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, 'target.s'), 'w') as f:
    f.write(f'\t.syntax unified\n\t.cpu cortex-m4\n\t.fpu fpv4-sp-d16\n\t.thumb\n'
            f'\t.section .text.{name},"ax",%progbits\n'
            f'\t.global {name}\n\t.type {name}, %function\n\t.thumb_func\n{name}:\n')
    f.write('\n'.join(lines) + '\n')
subprocess.check_call([os.path.join(TOOLS, 'arm-none-eabi-as'), '-mcpu=cortex-m4', '-mthumb',
                       '-mfpu=fpv4-sp-d16', os.path.join(out, 'target.s'), '-o', os.path.join(out, 'target.o')])
print(f'{out}/target.o: {len(lines)} lines, {len(pool)} pool words')
