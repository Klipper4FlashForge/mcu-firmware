#!/usr/bin/env bash
# Set up one permuter directory for a function that still differs from stock.
#   newtarget.sh <function> <stock-addr-hex> <stock-size> <source file in tree> [outdir]
# e.g. newtarget.sh gpio_out_reset 08007fc0 136 src/stm32/gpio.c
# Produces base.c, target.o, compile.sh and settings.toml, then runs the
# permuter's --debug pass, whose "base score" must reflect only the known
# difference (a base.c that compiles differently from the tree is useless).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
export MCU_ROOT=${MCU_ROOT:-$(cd "$HERE/../.." && pwd)}
WORK=${MCU_WORK:-$MCU_ROOT/work}
TREE=${MCU_TREE:-$MCU_ROOT/klipper}
PERM=${MCU_PERMUTER:-$WORK/decomp-permuter}
FUNC=$1 ADDR=$2 SIZE=$3 SRC=$4 OUT=${5:-$WORK/perm/$1}
mkdir -p "$OUT"
# the exact compile line of the tree, minus dependency output
export PATH=$WORK/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH
( cd "$TREE" && make -n -W "$SRC" "out/${SRC%.c}.o" ) | grep -m1 arm-none-eabi-gcc \
    | sed 's/^ *arm-none-eabi-gcc //; s/ -MD / /; s/ -c .*//' > "$OUT/cflags"
export MCU_CFLAGS="$(cat "$OUT/cflags")"
cat > "$OUT/compile.sh" <<EOS
#!/bin/bash
# invoked as compile.sh input.c -o output.o with the tree's exact flags
export PATH=$WORK/gcc-arm-none-eabi-10.3-2021.10/bin:\$PATH
IN=\$(readlink -f "\$1"); OUT=\$(readlink -f "\$3")
cd $TREE && exec arm-none-eabi-gcc $(cat "$OUT/cflags") -w -c "\$IN" -o "\$OUT"
EOS
chmod +x "$OUT/compile.sh"
printf 'func_name = "%s"\ncompiler_type = "gcc"\nobjdump_command = "arm-none-eabi-objdump -drz -j .text.%s"\n' \
    "$FUNC" "$FUNC" > "$OUT/settings.toml"
python3 "$HERE/mkbase.py" "$SRC" "$FUNC" "$OUT"
python3 "$HERE/mktarget.py" "$FUNC" "$ADDR" "$SIZE" "$OUT"
( cd "$PERM" && python3 permuter.py "$OUT" --debug 2>&1 | grep -E 'base score|error|Error' ) || true
echo "run: cd $PERM && python3 permuter.py $OUT -j 4 --best-only --stop-on-zero"
