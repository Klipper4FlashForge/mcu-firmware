#!/usr/bin/env python3
"""Compare one of our functions against a stock address.

    fncmp.py <our-symbol> <stock-addr-hex> [-v] [--size N]

Uses the same normalisation and the same whole-image disassembly as
cmpfuncs.py, so its verdicts are consistent with the handler gate.  The
instruction compare folds literal-pool offsets away, so the raw bytes of
the nm -S range (or --size N) are compared too: EXACT means both agree,
INSTR-EXACT POOL-DIFF means the code matches but the pool words do not.
The build tree comes from MCU_TREE (see cmpfuncs.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmpfuncs as C

sym = sys.argv[1]
saddr = int(sys.argv[2], 16)
verbose = '-v' in sys.argv

syms = C.our_symbols()
if sym not in syms:
    cand = [s for s in syms if s.startswith(sym)]
    if not cand:
        print("no symbol %s" % sym)
        sys.exit(1)
    sym = cand[0]
oaddr, olen = syms[sym]
olen = C.size_arg(sys.argv, olen)

o = [C.norm(i) for i in C.disasm_elf(C.OURS_ELF, oaddr, olen)]
cut = next((k for k, x in enumerate(o) if x.startswith('.word')), len(o))
o = o[:cut]
s = [C.norm(i) for i in C.disasm_raw(C.STOCK_BIN, saddr, olen + 64, C.STOCK_BASE)]
s = s[:len(o)]

pre = 0
while pre < min(len(o), len(s)) and o[pre] == s[pre]:
    pre += 1
eq = sum(1 for a, b in zip(o, s) if a == b)
insn_exact = pre == len(o) and bool(o)
nb, size, bdiff = C.bytes_equal(oaddr, saddr, olen)
print("%s  ours 0x%08X (%d insn)  stock 0x%08X   prefix %d, %d/%d equal%s"
      % (sym, oaddr, len(o), saddr, pre, eq, len(o),
         C.verdict(insn_exact, nb, size)))
print("BYTES %d/%d" % (nb, size))
if verbose and insn_exact and bdiff:
    for w in sorted(set(i & ~3 for i in bdiff)):
        print("  pool word +0x%02x differs (ours 0x%08X, stock 0x%08X)"
              % (w, C.word_at(C.OURS_BIN, oaddr + w),
                 C.word_at(C.STOCK_BIN, saddr + w)))
if verbose and pre < len(o):
    for i in range(max(len(o), len(s))):
        a = o[i] if i < len(o) else ''
        b = s[i] if i < len(s) else ''
        print("%-3d %-36s %-34s%s" % (i, a, b, '' if a == b else '  <<<'))
