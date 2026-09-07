#!/usr/bin/env bash
# Prove that the recovered source reproduces the stock levelBoard image
# byte for byte.  Refuses to run against uncommitted edits, so a pass is a
# statement about what is committed in klipper/ and not about whatever
# happens to be in the working tree.
#
#   ./test/verify.sh [<work-dir>]
#
# Exits non-zero on the first gate that fails.  Nothing here is advisory:
# a single differing byte is a failure.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:-$ROOT/work}"
STOCK="$ROOT/mcu/levelBoard/stock/levelBoard.bin"
OURS="$ROOT/klipper/out/klipper.bin"

EXPECT_MD5=156366b40ccc51f5768e083fa8ead210
EXPECT_SIZE=26704

fail() { echo "FAIL: $*" >&2; exit 1; }

# 0. the tree under test is the committed one
dirty=$(git -C "$ROOT" status --porcelain -- klipper 2>/dev/null || true)
if [ -n "$dirty" ]; then
    echo "$dirty" >&2
    fail "klipper/ has uncommitted changes; commit them or stash before verifying"
fi
echo "ok  tree             clean at $(git -C "$ROOT" rev-parse --short HEAD)"
echo
echo "== building"
"$ROOT/build.sh" "$WORK"

echo
echo "== gates"

[ -f "$OURS" ] || fail "no build output at $OURS"

# 1. the stock image is the one this recovery was measured against
got=$(md5sum "$STOCK" | cut -d' ' -f1)
[ "$got" = "$EXPECT_MD5" ] || fail "stock image is not the expected one ($got)"
echo "ok  stock image      md5 $EXPECT_MD5"

# 2. size
size=$(stat -c%s "$OURS")
[ "$size" = "$EXPECT_SIZE" ] || fail "size $size, expected $EXPECT_SIZE"
echo "ok  size             $size bytes"

# 3. md5 of our build
got=$(md5sum "$OURS" | cut -d' ' -f1)
[ "$got" = "$EXPECT_MD5" ] || fail "our md5 $got, expected $EXPECT_MD5"
echo "ok  our build        md5 $got"

# 4. the gate that actually matters: not one differing byte
if ! cmp -s "$OURS" "$STOCK"; then
    n=$(cmp -l "$OURS" "$STOCK" | wc -l)
    fail "$n differing bytes"
fi
echo "ok  cmp              0 differing bytes"

# 5. every function at stock's own address, every instruction identical.
# relocmap prints its summary block first and a per-function listing after,
# so keep the summary lines rather than the head or tail of the output.
if [ -x "$ROOT/tools/relocmap.py" ]; then
    out=$(cd "$ROOT" && MCU_WORK="$WORK" python3 tools/relocmap.py --all --limit 0 2>/dev/null)
    sum=$(echo "$out" | grep -E '^(functions:|instruction-exact:|  (EXACT-AT-ADDR|LAYOUT-DIFF|LITERAL-DIFF|CODE-DIFF) +[0-9]+$)')
    for k in LAYOUT-DIFF LITERAL-DIFF CODE-DIFF; do
        echo "$sum" | grep -qE "^  $k +0$" \
            || { echo "$sum" >&2; fail "relocmap reports $k"; }
    done
    echo "$sum" | grep -q '(100.0%)' \
        || { echo "$sum" >&2; fail "relocmap is not at 100% instructions"; }
    exact=$(echo "$sum" | grep -oE 'EXACT-AT-ADDR +[0-9]+' | grep -oE '[0-9]+')
    total=$(echo "$sum" | grep -oE '^functions: [0-9]+' | grep -oE '[0-9]+')
    echo "ok  functions        $exact/$total at stock's own address"
    echo "ok  instructions     $(echo "$sum" | grep -oE '[0-9]+/[0-9]+ instructions \(100\.0%\)')"
fi

# 6. all 54 command handlers instruction-identical
if [ -x "$ROOT/tools/cmpfuncs.py" ]; then
    out=$(cd "$ROOT" && MCU_WORK="$WORK" python3 tools/cmpfuncs.py 2>/dev/null)
    tally=$(echo "$out" | grep -E '^SAME [0-9]+ +DIFF [0-9]+ +NOSYM [0-9]+$')
    echo "$tally" | grep -qE 'DIFF 0 +NOSYM 0' \
        || { echo "$tally" >&2; fail "cmpfuncs reports differing handlers"; }
    echo "ok  handlers         $(echo "$tally" | grep -oE '^SAME [0-9]+' | grep -oE '[0-9]+')/$(echo "$tally" | grep -oE '^SAME [0-9]+' | grep -oE '[0-9]+') instruction-identical"
fi

echo
echo "PASS: the rebuild is byte-identical to the stock levelBoard image."
