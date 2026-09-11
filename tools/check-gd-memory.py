#!/usr/bin/env python3
"""Full-body C gate for small microlib memory/string helpers, not assembly.

The shared copy/move body has void AEABI ABI, unlike C memcpy/memmove.
ALIASES names identical entries, never additional bodies or byte coverage.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

from gd_function_gate import main, ROOT

UNITS = {name: ('runtime_memory.c', [define]) for name, define in [
    ('memory_copy', 'GD_MEMORY_COPY'), ('memory_set', 'GD_MEMORY_SET'),
    ('memory_clear', 'GD_MEMORY_CLEAR'), ('memory_c_set', 'GD_MEMORY_C_SET'),
    ('memory_compare', 'GD_MEMORY_COMPARE'), ('memory_search', 'GD_MEMORY_SEARCH')
]}
CASES = [
    ('__aeabi_memmove', 0x080003f4, 64),
    ('__aeabi_memset', 0x08000434, 14),
    ('__aeabi_memclr', 0x08000442, 4),
    ('memset', 0x08000446, 18),
    ('strcmp', 0x08000458, 28),
    ('memchr', 0x08000474, 20),
]
CASE_UNITS = dict(zip((case[0] for case in CASES), UNITS))
SYMBOLS = {'__aeabi_memset': 0x08000435}
ALIASES = {'__aeabi_memcpy': '__aeabi_memmove'}


def self_test():
    """Native C behavioral checks, separate from ARM byte matching.

    This uses the same bodies on ordinary valid buffers. It does not prove
    target instruction timing or proprietary AEABI clobber conventions.
    """
    harness = r'''
#include "runtime_memory.h"
#include <stdint.h>
#include <stdio.h>

#define CHECK(x) do { if (!(x)) return __LINE__; } while (0)
int main(void)
{
    unsigned char actual[160], expected[160], temporary[80];
    /* Every alignment, both overlap directions, equality, and disjoint data. */
    for (unsigned source = 0; source < 40; ++source)
        for (unsigned destination = 0; destination < 40; ++destination)
            for (unsigned count = 0; count <= 80; ++count) {
                for (unsigned i = 0; i < sizeof actual; ++i)
                    expected[i] = actual[i] = (unsigned char)(i * 37 + 19);
                for (unsigned i = 0; i < count; ++i)
                    temporary[i] = expected[source + i];
                for (unsigned i = 0; i < count; ++i)
                    expected[destination + i] = temporary[i];
                __aeabi_memmove(actual + destination, actual + source, count);
                for (unsigned i = 0; i < sizeof actual; ++i)
                    CHECK(actual[i] == expected[i]);
            }
    for (unsigned count = 0; count < 80; ++count)
        for (unsigned offset = 0; offset < 4; ++offset)
            for (int value = -257; value <= 513; value += 7) {
                for (unsigned i = 0; i < sizeof actual; ++i)
                    actual[i] = 0xa5;
                __aeabi_memset(actual + offset, count, value);
                for (unsigned i = 0; i < sizeof actual; ++i)
                    CHECK(actual[i] == (i >= offset && i < offset + count
                                       ? (unsigned char)value : 0xa5));
                CHECK(memset(actual + offset, value, count) == actual + offset);
                __aeabi_memclr(actual + offset, count);
                for (unsigned i = 0; i < count; ++i)
                    CHECK(actual[offset + i] == 0);
            }
    CHECK(strcmp("", "") == 0);
    CHECK(strcmp("same", "same") == 0);
    CHECK(strcmp("prefix", "prefixX") == -'X');
    for (unsigned a = 0; a < 256; ++a)
        for (unsigned b = 0; b < 256; ++b) {
            char left[] = {'x', (char)a, 0};
            char right[] = {'x', (char)b, 0};
            CHECK(strcmp(left, right) == (int)a - (int)b);
        }
    for (unsigned i = 0; i < sizeof actual; ++i)
        actual[i] = (unsigned char)(i % 17);
    for (unsigned count = 0; count <= sizeof actual; ++count)
        for (int value = -257; value <= 513; ++value) {
            void *wanted = 0;
            for (unsigned i = 0; i < count; ++i)
                if (actual[i] == (unsigned char)value) {
                    wanted = actual + i;
                    break;
                }
            CHECK(memchr(actual, value, count) == wanted);
        }
    puts("PASS: C memory overlap/alignment, zero counts, unsigned bytes, truncation and returns.");
    return 0;
}
'''
    source_dir = ROOT / 'mcu/mainBoardGD/recovered'
    with tempfile.TemporaryDirectory(prefix='gd-memory-test-') as directory:
        path = Path(directory)
        objects = []
        for unit, (source, defines) in UNITS.items():
            obj = path / (unit + '.o')
            subprocess.run(['cc', '-O2', '-fno-builtin', '-Wall', '-Wextra', '-Werror',
                            *['-D' + define for define in defines], '-c', str(source_dir / source),
                            '-o', str(obj)], check=True)
            objects.append(str(obj))
        test = path / 'test.c'
        test.write_text(harness)
        executable = path / 'test'
        subprocess.run(['cc', '-O2', '-fno-builtin', '-I', str(source_dir), str(test),
                        *objects, '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    else:
        raise SystemExit(main('memory', CASES, UNITS, CASE_UNITS, SYMBOLS))
