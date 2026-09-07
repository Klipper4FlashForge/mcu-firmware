#!/bin/bash
# usage: flagsweep.sh <tree-copy> <flags...>  -- one summary line per flag set.
# The tree copy's Makefile must append $(XFLAGS) to CFLAGS; never point this at
# work/klipper itself (it deletes objects and rebuilds).
ROOT=${MCU_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
TREE=$1; shift
export PATH=$ROOT/work/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH
export KLIPPER_BUILD_VERSION='?-20260609_102247-zhengxiaomming' KLIPPER_ZLIB=$ROOT/work/libz-classic.so
cd $TREE
export MCU_ROOT=$ROOT
for X in "$@"; do
  find out -name '*.o' -delete 2>/dev/null; rm -f out/klipper.elf out/klipper.bin
  if ! make -j8 XFLAGS="$X" >/dev/null 2>$TREE/../make.err; then echo "$X  BUILD-FAIL $(grep -m1 error $TREE/../make.err)"; continue; fi
  python3 - "$X" <<'PY'
import sys,os,subprocess
X=sys.argv[1]
ROOT=os.environ['MCU_ROOT']
ours=open('out/klipper.bin','rb').read(); stock=open(ROOT+'/mcu/levelBoard/stock/levelBoard.bin','rb').read()
same=sum(1 for a,b in zip(ours,stock) if a==b)
res=[]
env=dict(os.environ, MCU_TREE=os.getcwd())
for f in ['ff_eddy_update','ff_eddy_check_trigger','ff_eddy_rebaseline','DMA_Init','TIM_ETRClockMode2Config','gpio_out_reset']:
    nm=subprocess.run([ROOT+'/work/gcc-arm-none-eabi-10.3-2021.10/bin/arm-none-eabi-nm',ROOT+'/work/klipper/out/klipper.elf'],capture_output=True,text=True).stdout
    a=[l.split()[0] for l in nm.splitlines() if l.endswith(' '+f)]
    if not a: res.append(f+':nosym'); continue
    o=subprocess.run(['python3',ROOT+'/tools/fncmp.py',f,a[0]],capture_output=True,text=True,env=env,cwd=ROOT).stdout
    import re
    m=re.search(r'(\d+)/(\d+) equal',o); res.append('%s:%s'%(f[:12],m.group(1)+'/'+m.group(2) if m else '?'))
print('%-40s size=%d same=%d  %s'%(X,len(ours),same,' '.join(res)))
PY
done
