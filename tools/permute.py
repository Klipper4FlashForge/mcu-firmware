#!/usr/bin/env python3
"""Search source variants for one that compiles to the stock instructions.

Register allocation and scheduling differences cannot be argued into place:
the compiler is pinned, so where our code still differs the *source* must
differ.  This tries a list of semantically equivalent formulations of one
function, rebuilds each, and reports which (if any) reproduces stock's
instruction stream -- the standard technique in matching decompilation.

    permute.py <handler-name> <file> <variants.py>

<variants.py> must define ORIGINAL (the exact current text) and VARIANTS
(a list of replacement strings).
"""
import importlib.util
import os
import subprocess
import sys

# Same convention as every other tool here: MCU_WORK names the build dir
# build.sh was pointed at, and everything else hangs off it.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('MCU_ROOT', os.getcwd())
WORK = os.environ.get('MCU_WORK', os.path.join(ROOT, 'work'))
TREE = os.environ.get('MCU_TREE', os.path.join(ROOT, 'klipper'))
SRC = os.path.join(TREE, 'src') + '/'


def load(path):
    spec = importlib.util.spec_from_file_location('variants', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.ORIGINAL, m.VARIANTS


def build():
    env = dict(os.environ)
    env['PATH'] = os.path.join(
        WORK, 'gcc-arm-none-eabi-10.3-2021.10/bin') + ':' + env['PATH']
    env.setdefault('KLIPPER_BUILD_VERSION', '?-20260609_102247-zhengxiaomming')
    env.setdefault('KLIPPER_ZLIB', os.path.join(WORK, 'libz-classic.so'))
    return subprocess.run(['make', '-j%d' % (os.cpu_count() or 4)], cwd=TREE,
                          capture_output=True, text=True, env=env).returncode == 0


def check(handler):
    """Return (matched, description) for one handler.

    The description carries the matching-prefix length, which is what makes
    the search steerable: a variant that agrees for 9 instructions before
    diverging is closer than one that diverges at 0, even though neither
    matches.
    """
    out = subprocess.run(['python3', os.path.join(HERE, 'cmpfuncs.py')],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == handler:
            return parts[0] == 'SAME', line.strip()
    return False, '(not found)'


def main():
    handler, path, vpath = sys.argv[1], SRC + sys.argv[2], sys.argv[3]
    original, variants = load(vpath)
    text = open(path).read()
    if original not in text:
        print("ORIGINAL not present in %s" % path)
        return 1
    try:
        for i, v in enumerate(variants):
            open(path, 'w').write(text.replace(original, v, 1))
            if not build():
                print("variant %d: BUILD FAILED" % i)
                continue
            same, line = check(handler)
            print("variant %d: %s%s" % (i, 'MATCH  ' if same else '       ', line))
            if same:
                print("\nkeeping variant %d" % i)
                return 0
    finally:
        pass
    open(path, 'w').write(text)          # nothing matched; restore
    build()
    print("\nno variant matched; source restored")
    return 1


sys.exit(main())
