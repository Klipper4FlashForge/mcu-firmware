#!/usr/bin/env bash
# Fetch decomp-permuter (the matching-decompilation community's random
# source permuter) at a pinned commit and apply the two local changes it
# needs for this project:
#   - accept R_ARM_THM_JUMP24/JUMP19 relocations (GCC tail calls)
#   - keep every other function body in the candidate source: GCC -O2
#     inlines statics and globals into the target and drops stores to
#     write-only statics, so the candidate must see the whole unit.
# Usage: setup.sh [dest-dir]   (default: work/decomp-permuter)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=${MCU_ROOT:-$(cd "$HERE/../.." && pwd)}
DEST=${1:-$ROOT/work/decomp-permuter}
COMMIT=6786c403af1166b507c388822685d4fcd893b282
if [ ! -d "$DEST/.git" ]; then
    git clone -q https://github.com/simonlindholm/decomp-permuter.git "$DEST"
fi
git -C "$DEST" fetch -q origin "$COMMIT" 2>/dev/null || true
git -C "$DEST" checkout -q "$COMMIT"
git -C "$DEST" apply --check "$HERE/decomp-permuter-local.patch" 2>/dev/null \
    && git -C "$DEST" apply "$HERE/decomp-permuter-local.patch"
python3 -c 'import pycparser' 2>/dev/null || pip3 install --user pycparser
echo "decomp-permuter ready in $DEST"
