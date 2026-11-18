#!/bin/bash
# idac DC: every range x every code, 5 corners x {0,27,85} C, outputs held at 1.0 V (+0.5/2.5 V at tt/ff/ss)
cd /work/sim/tb/bias; mkdir -p out/corners
jobs=()
for c in tt ff ss fs sf; do for t in 0 27 85; do jobs+=("$c $t 1.0"); done; done
for c in tt ff ss; do for t in 27 85; do for v in 0.5 2.5; do jobs+=("$c $t $v"); done; done; done
printf '%s\n' "${jobs[@]}" | xargs -P 8 -L 1 bash -c '
  f=out/corners/idac_$0_$1_$2; python3 gen_idac.py $f.cir --corner $0 --temp $1 --vout $2
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
python3 analyze_idac.py out/corners > out/idac_corners_summary.txt
cat out/idac_corners_summary.txt
