#!/usr/bin/env python3
"""Map rebuilt functions into stock and compare their literal-pool values.

This is a no-build diagnostic.  It first requires an instruction-exact match
(using cmpfuncs.norm), then pairs PC-relative literal loads in the two copies.
That separates recovered source from remaining address/layout differences.
The source column is the rebuilt compilation unit reported by DWARF.
"""
import argparse
from collections import Counter, defaultdict
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmpfuncs as C

TREE = C.TREE
OURS_BIN = C.OURS_BIN

INSN = re.compile(r'\s*([0-9a-f]+):\s+([0-9a-f ]+)\t(\S+)\s*(.*)')
FUNC = re.compile(r'^([0-9a-f]+) <(.+)>:$')
LITERAL = re.compile(r'\[pc,\s*#(-?(?:0x[0-9a-f]+|\d+))\]', re.I)
LOC = re.compile(
    r'^([0-9a-f]+)(?:\s+[0-9a-f]+)?\s+\S\s+(\S+)(?:\t(.+?):\d+)?$')


def run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def parse_stream(lines):
    """Return functions as (name, address, [(address, mnemonic, operands)])."""
    funcs = []
    name = None
    address = None
    seq = []
    for line in lines:
        fm = FUNC.match(line)
        if fm:
            if name is not None and seq:
                funcs.append((name, address, seq))
            address = int(fm.group(1), 16)
            name = fm.group(2)
            seq = []
            continue
        im = INSN.match(line)
        if im and name is not None:
            seq.append((int(im.group(1), 16), im.group(3), im.group(4)))
    if name is not None and seq:
        funcs.append((name, address, seq))
    return funcs


def stock_stream():
    out = run([C.OBJDUMP, '-D', '-b', 'binary', '-m', 'arm', '-M',
               'force-thumb', '--adjust-vma=0x%x' % C.STOCK_BASE,
               C.STOCK_BIN])
    seq = []
    for line in out.splitlines():
        m = INSN.match(line)
        if m:
            seq.append((int(m.group(1), 16), m.group(3), m.group(4)))
    return seq


def source_locations():
    """Map linked function addresses to their DWARF compilation units."""
    locations = {}
    out = run([C.NM, '-nSl', '--defined-only', C.OURS_ELF])
    for line in out.splitlines():
        m = LOC.match(line)
        if not m or not m.group(3):
            continue
        path = m.group(3)
        tree_prefix = os.path.abspath(TREE) + os.sep
        if path.startswith(tree_prefix):
            path = path[len(tree_prefix):]
        else:
            marker = path.find('src/')
            if marker >= 0:
                path = path[marker:]
        locations[int(m.group(1), 16)] = path
    return locations


def code_only(seq):
    cut = next((i for i, (_, mn, _) in enumerate(seq)
                if mn.startswith('.word')), len(seq))
    return seq[:cut]


def literal_value(blob, address, base):
    off = address - base
    if off < 0 or off + 4 > len(blob):
        return None
    return struct.unpack_from('<I', blob, off)[0]


def literals(seq, blob, base):
    values = []
    for address, mnemonic, operands in seq:
        # Thumb ldr/ldr.w with PC as base is a literal load.  Register-offset
        # loads and ADR are deliberately excluded.
        if not mnemonic.startswith('ldr'):
            continue
        m = LITERAL.search(operands)
        if not m:
            continue
        offset = int(m.group(1), 0)
        pool = ((address + 4) & ~3) + offset
        values.append((address, pool, literal_value(blob, pool, base)))
    return values


def region(value):
    if value is None:
        return 'outside'
    if 0x08000000 <= value < 0x08100000:
        return 'flash'
    if 0x20000000 <= value < 0x20100000:
        return 'ram'
    if 0x40000000 <= value < 0x60000000 or 0xE0000000 <= value < 0xF0000000:
        return 'peripheral'
    return 'constant'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true',
                        help='print every function, not only unresolved rows')
    parser.add_argument('--limit', type=int, default=40,
                        help='maximum detail rows (default: 40; 0 is unlimited)')
    args = parser.parse_args()

    ours_blob = open(OURS_BIN, 'rb').read()
    stock_blob = open(C.STOCK_BIN, 'rb').read()
    ours_out = run([C.OBJDUMP, '-d', C.OURS_ELF])
    ours = parse_stream(ours_out.splitlines())
    stock = stock_stream()
    sources = source_locations()

    index = defaultdict(list)
    for i, insn in enumerate(stock):
        index[C.norm(insn[1:])].append(i)

    rows = []
    counts = Counter()
    unit_counts = defaultdict(Counter)
    compared_insns = exact_insns = 0
    for name, ours_addr, raw_seq in ours:
        seq = code_only(raw_seq)
        if len(seq) < 2:
            continue
        norm = [C.norm(x[1:]) for x in seq]
        compared_insns += len(norm)
        hits = [i for i in index.get(norm[0], [])
                if [C.norm(x[1:]) for x in stock[i:i + len(norm)]] == norm]
        source = sources.get(ours_addr, '?')
        if not hits:
            status = 'CODE-DIFF'
            counts[status] += 1
            unit_counts[source][status] += 1
            rows.append((status, name, ours_addr, None, len(norm), 0, 0,
                         source, []))
            continue

        # Repeated tiny routines can have many matches.  Nearest placement is
        # the least surprising representative; retain the hit count in output.
        hit = min(hits, key=lambda i: abs(stock[i][0] - ours_addr))
        stock_addr = stock[hit][0]
        stock_seq = stock[hit:hit + len(norm)]
        olit = literals(seq, ours_blob, C.STOCK_BASE)
        slit = literals(stock_seq, stock_blob, C.STOCK_BASE)
        pairs = []
        for o, s in zip(olit, slit):
            pairs.append((o[2], s[2], region(o[2]), region(s[2])))
        literal_bad = sum(1 for o, s, _, _ in pairs if o != s)
        literal_shape_bad = len(olit) != len(slit)
        if literal_shape_bad or literal_bad:
            status = 'LITERAL-DIFF'
        elif ours_addr != stock_addr:
            status = 'LAYOUT-DIFF'
        else:
            status = 'EXACT-AT-ADDR'
        counts[status] += 1
        unit_counts[source][status] += 1
        exact_insns += len(norm)
        rows.append((status, name, ours_addr, stock_addr, len(norm),
                     len(hits), literal_bad, source, pairs))

    total = sum(counts.values())
    print('functions: %d' % total)
    for status in ('EXACT-AT-ADDR', 'LAYOUT-DIFF', 'LITERAL-DIFF', 'CODE-DIFF'):
        print('  %-14s %3d' % (status, counts[status]))
    print('instruction-exact: %d/%d functions; %d/%d instructions (%.1f%%)'
          % (total - counts['CODE-DIFF'], total, exact_insns,
             compared_insns, 100.0 * exact_insns / compared_insns))

    literal_deltas = Counter()
    for row in rows:
        for ours_value, stock_value, ours_region, stock_region in row[8]:
            if ours_value != stock_value:
                delta = None if ours_value is None or stock_value is None \
                    else ours_value - stock_value
                literal_deltas[(ours_region, stock_region, delta)] += 1
    if literal_deltas:
        print('\nmost common differing literal relocations:')
        for (ours_region, stock_region, delta), count in literal_deltas.most_common(10):
            dtext = '?' if delta is None else '%+d' % delta
            print('  %3d  %-10s -> %-10s %s'
                  % (count, ours_region, stock_region, dtext))

    print('\ncompilation units with unresolved functions:')
    ranked = []
    for unit, c in unit_counts.items():
        unresolved = c['CODE-DIFF'] + c['LITERAL-DIFF'] + c['LAYOUT-DIFF']
        if unresolved:
            ranked.append((c['CODE-DIFF'], c['LITERAL-DIFF'],
                           c['LAYOUT-DIFF'], unit, c))
    for _, _, _, unit, c in sorted(ranked, reverse=True):
        print('  %-38s code=%2d literal=%2d layout=%2d exact=%2d'
              % (unit, c['CODE-DIFF'], c['LITERAL-DIFF'],
                 c['LAYOUT-DIFF'], c['EXACT-AT-ADDR']))

    detail = rows if args.all else [r for r in rows if r[0] != 'EXACT-AT-ADDR']
    order = {'CODE-DIFF': 0, 'LITERAL-DIFF': 1, 'LAYOUT-DIFF': 2,
             'EXACT-AT-ADDR': 3}
    detail.sort(key=lambda r: (order[r[0]], -r[4], r[1]))
    if args.limit:
        detail = detail[:args.limit]
    print('\ndetail:')
    for status, name, oa, sa, ninsn, nhit, nbad, source, pairs in detail:
        target = '-' if sa is None else '0x%08x (%+d)' % (sa, oa - sa)
        print('  %-12s %-31s ours=0x%08x stock=%-18s %3di  '
              'hits=%-2d badlit=%-2d %s'
              % (status, name, oa, target, ninsn, nhit, nbad, source))
        for ov, sv, ore, sre in pairs:
            if ov != sv:
                print('      literal ours=%s (%s) stock=%s (%s) delta=%s'
                      % ('?' if ov is None else '0x%08x' % ov, ore,
                         '?' if sv is None else '0x%08x' % sv, sre,
                         '?' if ov is None or sv is None else '%+d' % (ov - sv)))


if __name__ == '__main__':
    main()
