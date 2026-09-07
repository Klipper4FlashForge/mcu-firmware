#!/usr/bin/env bash
# Rebuild the levelBoard MCU firmware from the recovered source in
# klipper/, and check the result against the stock image.
#
# klipper/ is unmodified upstream Klipper at the base commit plus exactly
# one commit, the recovery itself.  The build runs in that tree; its output
# (out/, .config) is gitignored, so `git status klipper/` still shows only
# real source edits.  test/verify.sh refuses to run on a dirty tree, which
# is what makes its result a statement about the committed source.
#
#   ./build.sh [<work-dir>]
#
# Three things have to be pinned before any of this is reproducible at all:
#
#   * the version stamp.  Klipper bakes "?-<timestamp>-<hostname>" into the
#     data dictionary it embeds in the image, so two builds a second apart
#     differ.  KLIPPER_BUILD_VERSION pins it to what the stock image reports.
#   * the compiler.  The stock image names it in build_versions.
#   * zlib.  The dictionary is stored deflated, and Fedora's Python links
#     zlib-ng, whose output differs byte for byte from classic zlib at the
#     same level.  We build classic zlib and deflate through it.
#
# With those pinned the build is byte-reproducible, and the embedded
# dictionary blob comes out identical to the stock firmware's.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE"
BOARD="$ROOT/mcu/levelBoard"
TOOLS="$ROOT/tools"
WORK="${1:-$ROOT/work}"
JOBS="${MCU_BUILD_JOBS:-1}"
case "$JOBS" in
    1|2) ;;
    *) echo "MCU_BUILD_JOBS must be 1 or 2 (got: $JOBS)" >&2; exit 2 ;;
esac

# A dictionary-compatible upstream commit used for reconstruction, and the
# exact toolchain named by the stock image's build_versions string.
# Recorded for provenance; klipper/ is already this commit plus the
# recovery commit, so nothing here checks it out.
KLIPPER_BASE=6d70050261ec3290f3c2e4015438e4910fd430d0
TOOLCHAIN_VER=10.3-2021.10
TOOLCHAIN_URL="https://developer.arm.com/-/media/Files/downloads/gnu-rm/${TOOLCHAIN_VER}/gcc-arm-none-eabi-${TOOLCHAIN_VER}-x86_64-linux.tar.bz2"
TOOLCHAIN_SHA256=97dbb4f019ad1650b732faffcc881689cedc14e2b7ee863d390e0a41ef16c9a3

# Classic zlib.  Fedora's Python links zlib-ng, whose deflate output differs
# byte for byte at the same level, so the dictionary blob would not match.
ZLIB_URL=https://zlib.net/fossils/zlib-1.3.1.tar.gz
ZLIB_SHA256=9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23

# The stock image's own version stamp, read out of its data dictionary.
export KLIPPER_BUILD_VERSION='?-20260609_102247-zhengxiaomming'

STOCK_BIN="${STOCK_BIN:-$ROOT/mcu/levelBoard/stock/levelBoard.bin}"
STOCK_DICT="${STOCK_DICT:-$ROOT/mcu/levelBoard/stock/levelBoard.dict.json}"

mkdir -p "$WORK"
exec 9>"$WORK/.build.lock"
flock 9

# -- toolchain ---------------------------------------------------------
TC="$WORK/gcc-arm-none-eabi-${TOOLCHAIN_VER}"
if [ ! -x "$TC/bin/arm-none-eabi-gcc" ]; then
    echo ">> fetching GCC ARM ${TOOLCHAIN_VER}"
    curl -sSL -o "$WORK/gcc-arm.tar.bz2" "$TOOLCHAIN_URL"
    printf '%s  %s\n' "$TOOLCHAIN_SHA256" "$WORK/gcc-arm.tar.bz2" \
        | sha256sum -c -
    tar -xjf "$WORK/gcc-arm.tar.bz2" -C "$WORK"
fi
export PATH="$TC/bin:$PATH"
arm-none-eabi-gcc --version | head -n1

# -- classic zlib ------------------------------------------------------
if [ ! -f "$WORK/libz-classic.so" ]; then
    echo ">> building classic zlib"
    if [ ! -f "$WORK/zlib-1.3.1.tar.gz" ]; then
        curl -sSL -o "$WORK/zlib-1.3.1.tar.gz" "$ZLIB_URL"
    fi
    printf '%s  %s\n' "$ZLIB_SHA256" "$WORK/zlib-1.3.1.tar.gz" | sha256sum -c -
    tar -xzf "$WORK/zlib-1.3.1.tar.gz" -C "$WORK"
    ( cd "$WORK/zlib-1.3.1" && CFLAGS=-fPIC ./configure >/dev/null 2>&1 \
        && make -j"$JOBS" >/dev/null 2>&1 \
        && cp libz.so.1.3.1 "$WORK/libz-classic.so" )
fi
export KLIPPER_ZLIB="$WORK/libz-classic.so"

# -- the recovered tree -------------------------------------------------
SRC="$ROOT/klipper"
[ -f "$SRC/src/ff_flashforge.c" ] \
    || { echo "!! $SRC is not the recovered tree" >&2; exit 1; }

# -- build -------------------------------------------------------------
cp "$BOARD/levelBoard.config" "$SRC/.config"
( cd "$SRC" && python3 lib/kconfiglib/olddefconfig.py src/Kconfig >/dev/null )
( cd "$SRC" && make -j"$JOBS" >/dev/null )
echo ">> built $(stat -c%s "$SRC/out/klipper.bin") bytes (stock: $(stat -c%s "$STOCK_BIN" 2>/dev/null || echo '?'))"

# -- gates -------------------------------------------------------------
if [ ! -f "$STOCK_DICT" ]; then
    echo "   !! no stock dictionary at $STOCK_DICT" >&2
    echo "      run: ./tools/extract-dict.py \\" >&2
    echo "             mcu/levelBoard/stock/levelBoard.bin $STOCK_DICT" >&2
    exit 1
fi

python3 "$TOOLS/compare-dict.py" "$SRC/out/klipper.dict" "$STOCK_DICT"
STOCK_BIN="$STOCK_BIN" python3 "$TOOLS/compare-blob.py" "$SRC/out" "$STOCK_BIN"
