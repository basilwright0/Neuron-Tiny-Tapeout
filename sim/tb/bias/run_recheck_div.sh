#!/bin/bash
# Rev B master: ext /1 vs ext /16 vs internal reference; tt/ss/ff at 27 C, ranges 0,3,5 codes 1,16,31
cd /work/sim/tb/bias; mkdir -p out/recheck/div
jobs=()
for c in tt ss ff; do
  jobs+=("$c 0 8e-6 a") jobs+=("$c 0 16e-6 a") jobs+=("$c 1 128e-6 a") jobs+=("$c 1 256e-6 a") jobs+=("$c 2 0 a") jobs+=("$c 3 0 a")
done
printf '%s\n' "${jobs[@]}" | xargs -P 1 -L 1 bash -c '
  f=out/recheck/div/m$1_$0_i$2; python3 gen_idac.py $f.cir --corner $0 --mode $1 --iref $2 --ranges 0,3,5 --codes 1,16,31
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
python3 analyze_div.py > out/recheck/div_summary.txt; cat out/recheck/div_summary.txt
