#!/bin/bash
# leakage floor + shifted-source benefit: ranges 4,5, codes 0,1,2,8,31 ; tt/ff/ss x 27/85 ; Vout 0.5/2.5 ; shift vs noshift
cd /work/sim/tb/bias; mkdir -p out/floor
jobs=()
for c in tt ff ss; do for t in 27 85; do for v in 0.5 2.5; do jobs+=("$c $t $v x"); jobs+=("$c $t $v --noshift"); done; done; done
printf '%s\n' "${jobs[@]}" | xargs -P 8 -L 1 bash -c '
  s=$3; [ "$s" = x ] && s=""; f=out/floor/idac_$0_$1_$2${s:+_noshift}
  python3 gen_idac.py $f.cir --corner $0 --temp $1 --vout $2 --ranges 4,5 --codes 0,1,2,8,31 $s
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
for f in out/floor/*.log; do echo "== $(basename $f .log)"; grep -E "^D " $f | awk "{printf \"r%s c%-2s n=%10.3e p=%10.3e\n\", \$2,\$3,(\$4<0?-\$4:\$4),(\$5<0?-\$5:\$5)}"; done > out/floor_summary.txt
