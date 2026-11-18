#!/bin/bash
# output compliance: Vout 0.2..3.1 V; r3 code 19 (150 pA), r1 code 20 (10 nA), r0 code 31 (FS), r4 code 10 ; tt/ff/ss 27/85
cd /work/sim/tb/bias; mkdir -p out/comp
jobs=()
for c in tt ff ss; do for t in 27 85; do jobs+=("$c $t 0 31"); jobs+=("$c $t 1 20"); jobs+=("$c $t 3 19"); jobs+=("$c $t 4 10"); done; done
printf '%s\n' "${jobs[@]}" | xargs -P 8 -L 1 bash -c '
  f=out/comp/comp_$0_$1_r$2; python3 gen_idac.py $f.cir --corner $0 --temp $1 --ranges $2 --codes $3 --vsweep
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
python3 analyze_comp.py out/comp > out/compliance_summary.txt; cat out/compliance_summary.txt
