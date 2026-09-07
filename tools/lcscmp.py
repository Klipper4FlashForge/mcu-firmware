#!/usr/bin/env python3
# usage: lcscmp.py <symbol> <stock-addr-hex> [-v] [--size N]
# Alignment-aware score: longest common subsequence of the normalised
# instruction streams, ours vs stock. fncmp.py counts positions, which
# punishes one inserted instruction for the whole rest of a function.
# The instruction compare folds literal-pool offsets away, so the raw bytes
# of the nm -S range (or --size N) are compared as well: EXACT needs both,
# INSTR-EXACT POOL-DIFF means only the pool words differ.
# The build tree comes from MCU_TREE (see cmpfuncs.py).
import sys,os,difflib
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('MCU_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import cmpfuncs as C
sym=sys.argv[1]; saddr=int(sys.argv[2],16)
syms=C.our_symbols(); oaddr,olen=syms[sym]
olen=C.size_arg(sys.argv,olen)
o=[C.norm(i) for i in C.disasm_elf(C.OURS_ELF,oaddr,olen)]
cut=next((k for k,x in enumerate(o) if x.startswith('.word')),len(o)); o=o[:cut]
s=[C.norm(i) for i in C.disasm_raw(C.STOCK_BIN,saddr,olen+64,C.STOCK_BASE)][:len(o)]
m=difflib.SequenceMatcher(None,o,s,autojunk=False)
lcs=sum(b.size for b in m.get_matching_blocks())
nb,size,bdiff=C.bytes_equal(oaddr,saddr,olen)
print('%s lcs=%d/%d%s'%(sym,lcs,len(o),C.verdict(lcs==len(o) and bool(o),nb,size)))
print('BYTES %d/%d'%(nb,size))
if '-v' in sys.argv:
    for tag,i1,i2,j1,j2 in m.get_opcodes():
        if tag!='equal': print(tag,i1,i2,'|',' ; '.join(o[i1:i2]),'||',' ; '.join(s[j1:j2]))
    if lcs==len(o) and bdiff:
        for w in sorted(set(i&~3 for i in bdiff)):
            print('  pool word +0x%02x differs (ours 0x%08X, stock 0x%08X)'%(w,C.word_at(C.OURS_BIN,oaddr+w),C.word_at(C.STOCK_BIN,saddr+w)))
