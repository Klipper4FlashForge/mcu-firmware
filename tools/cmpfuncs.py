#!/usr/bin/env python3
"""Compare each command handler in our build against the stock image.

Both sides are disassembled with the same binutils.  Control-flow targets and
pc-relative literal offsets are normalised away (the two images have different
layouts), so what is compared is the instruction stream: mnemonics, registers
and every data immediate.
"""
import json
import re
import subprocess
import sys

# Paths come from the environment so this runs against any build tree.
#   MCU_WORK   the build dir used by build.sh (default work)
#   MCU_TREE   the Klipper tree whose out/ is scored (default $MCU_WORK/klipper;
#              point it at $MCU_WORK/exp/<name> to score an experiment copy)
#   OURS_ELF / OURS_BIN / OURS_DICT   explicit overrides of single build outputs
#   STOCK_BIN / STOCK_DICT   the stock image and its extracted dictionary
# Every comparator imports these from here, so one convention covers them all.
import os

ROOT = os.environ.get('MCU_ROOT', os.getcwd())
WORK = os.environ.get('MCU_WORK', os.path.join(ROOT, 'work'))
TREE = os.environ.get('MCU_TREE', os.path.join(ROOT, 'klipper'))
TC = os.environ.get('MCU_TOOLCHAIN',
                    os.path.join(WORK, 'gcc-arm-none-eabi-10.3-2021.10'))
OBJDUMP = os.path.join(TC, 'bin/arm-none-eabi-objdump')
NM = os.path.join(TC, 'bin/arm-none-eabi-nm')
OURS_ELF = os.environ.get('OURS_ELF', os.path.join(TREE, 'out/klipper.elf'))
OURS_BIN = os.environ.get('OURS_BIN', os.path.join(TREE, 'out/klipper.bin'))
OURS_DICT = os.environ.get('OURS_DICT', os.path.join(TREE, 'out/klipper.dict'))
STOCK_BIN = os.environ.get('STOCK_BIN',
                           os.path.join(ROOT, 'mcu/levelBoard/stock/levelBoard.bin'))
STOCK_DICT = os.environ.get('STOCK_DICT',
                            os.path.join(ROOT, 'mcu/levelBoard/stock/levelBoard.dict.json'))
STOCK_BASE = 0x08004000
STOCK_TABLE = 0x0800A35C

HEX = re.compile(r'\b(?:0x)?[0-9a-f]{5,}\b')
CONTROL_FLOW = {
    'b', 'bl', 'blx', 'bx',
    'beq', 'bne', 'bcs', 'bcc', 'bmi', 'bpl', 'bvs', 'bvc',
    'bhi', 'bls', 'bge', 'blt', 'bgt', 'ble',
    'cbz', 'cbnz', 'adr',
}


def norm(insn):
    """Drop layout-dependent addresses while retaining data constants."""
    mnemonic = insn[0]
    op = insn[1]
    op = re.sub(r'\s*;.*$', '', op)
    op = re.sub(r'<[^>]*>', '', op)
    # pc-relative literal offsets follow the pool layout, not the code
    op = re.sub(r'\[pc, #\d+\]', '[pc, #A]', op)
    # Direct branch/call destinations also follow the final link layout.  Do
    # not apply this to every operand: large mov/add/cmp immediates are data
    # and must agree for a function to be called instruction-identical.
    if mnemonic.split('.')[0] in CONTROL_FLOW:
        op = HEX.sub('A', op)
    return mnemonic + ' ' + op.strip()


_RAW_CACHE = {}


def _disasm_whole(path, vma):
    """Disassemble a flat binary once, returning [(addr, mnemonic, ops)].

    Slicing this in Python replaces per-function --start-address calls,
    which cannot be trusted: for some addresses objdump emits nothing at
    all from a `-b binary` image even though neighbouring addresses work.
    """
    key = (path, vma)
    if key in _RAW_CACHE:
        return _RAW_CACHE[key]
    out = subprocess.run(
        [OBJDUMP, '-D', '-b', 'binary', '-m', 'arm', '-M', 'force-thumb',
         '--adjust-vma=0x%x' % vma, path],
        capture_output=True, text=True).stdout
    seq = []
    for line in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f ]+)\t(\S+)\s*(.*)', line)
        if m:
            seq.append((int(m.group(1), 16), m.group(3), m.group(4)))
    _RAW_CACHE[key] = seq
    return seq


def disasm_raw(path, start, length, vma):
    seq = _disasm_whole(path, vma)
    lo, hi = start, start + length
    insns = [(mn, ops) for a, mn, ops in seq if lo <= a < hi]
    return insns


def disasm_elf(path, start, length):
    out = subprocess.run(
        [OBJDUMP, '-d', '--start-address=0x%x' % start,
         '--stop-address=0x%x' % (start + length), path],
        capture_output=True, text=True).stdout
    insns = []
    for line in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f ]+)\t(\S+)\s*(.*)', line)
        if m:
            insns.append((m.group(3), m.group(4)))
    return insns


def bytes_equal(oaddr, saddr, size):
    """Count the bytes of our image at oaddr that equal stock's at saddr.

    norm() folds pc-relative literal offsets away, so two functions can be
    instruction-identical while the words in their literal pools differ.
    The raw bytes over the whole nm -S range (code plus pool) settle that.
    Returns (equal, size, [differing offsets within the function]).
    """
    ours = open(OURS_BIN, 'rb').read()
    stock = open(STOCK_BIN, 'rb').read()
    o = ours[oaddr - STOCK_BASE:oaddr - STOCK_BASE + size]
    s = stock[saddr - STOCK_BASE:saddr - STOCK_BASE + size]
    diff = [i for i in range(size)
            if i >= len(o) or i >= len(s) or o[i] != s[i]]
    return size - len(diff), size, diff


def word_at(path, addr):
    """The little-endian 32-bit word of an image at a load address."""
    data = open(path, 'rb').read()
    off = addr - STOCK_BASE
    return int.from_bytes(data[off:off + 4].ljust(4, b'\0'), 'little')


def verdict(insn_exact, nbytes, size):
    """EXACT needs both the instruction stream and the bytes to agree."""
    if not insn_exact:
        return ''
    return '   EXACT' if nbytes == size else '   INSTR-EXACT POOL-DIFF'


def size_arg(argv, default):
    """`--size N` overrides the nm -S size of the compared range."""
    if '--size' in argv:
        return int(argv[argv.index('--size') + 1], 0)
    return default


def our_symbols():
    out = subprocess.run([NM, '-S', '--defined-only', OURS_ELF],
                         capture_output=True, text=True).stdout
    syms = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 4 and p[2] in 'tT':
            syms[p[3]] = (int(p[0], 16), int(p[1], 16))
    return syms


def stock_table():
    """msgid -> handler address, from command_index[]."""
    d = open(STOCK_BIN, 'rb').read()
    j = json.load(open(STOCK_DICT))
    byenc = {}
    for name, mid in j['commands'].items():
        enc = mid if mid < 0x60 else ((0x80 | (mid >> 7)) << 8) | (mid & 0x7f)
        byenc[enc] = name
    out = {}
    off = STOCK_TABLE - STOCK_BASE
    for i in range(len(j['commands'])):
        o = off + 16 * i
        enc = int.from_bytes(d[o:o+2], 'little')
        fn = int.from_bytes(d[o+12:o+16], 'little') & ~1
        if enc in byenc:
            out[byenc[enc]] = fn
    return out


def main():
    d = open(STOCK_BIN, 'rb').read()
    stock_end = STOCK_BASE + len(d)
    handlers = stock_table()
    syms = our_symbols()
    ours_cmds = set(json.load(open(OURS_DICT))['commands'])

    # sorted handler addresses, to bound each stock function
    addrs = sorted(set(handlers.values()))

    same = diff = missing = 0
    rows = []
    for name in sorted(handlers):
        if name not in ours_cmds:
            continue
        short = name.split()[0]
        sym = 'command_' + short
        cand = [s for s in syms if s == sym or s.startswith(sym + '.')]
        if not cand:
            missing += 1
            rows.append(('NOSYM', short, '', ''))
            continue
        oaddr, olen = syms[cand[0]]
        saddr = handlers[name]
        nxt = next((a for a in addrs if a > saddr), stock_end)
        slen = min(max(nxt - saddr, 0x400), olen + 64)
        s = [norm(i) for i in disasm_raw(STOCK_BIN, saddr, slen, STOCK_BASE)]
        o = [norm(i) for i in disasm_elf(OURS_ELF, oaddr, olen)]
        # nm's size covers the literal pool too; code ends at the first .word
        cut = next((k for k, x in enumerate(o) if x.startswith('.word')), len(o))
        o = o[:cut]
        s = s[:len(o)]
        if s == o:
            same += 1
            rows.append(('SAME', short, '%d insn' % len(o), ''))
        else:
            diff += 1
            first = next((k for k in range(min(len(s), len(o)))
                          if s[k] != o[k]), min(len(s), len(o)))
            rows.append(('DIFF', short, 'ours %d / stock %d insn'
                         % (len(o), len(s)), 'first diff @%d' % first))
    for r in rows:
        print("  %-6s %-28s %-24s %s" % r)
    print("\nSAME %d   DIFF %d   NOSYM %d" % (same, diff, missing))


if __name__ == '__main__':
    main()
