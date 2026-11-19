#!/bin/bash
# Speed track: slot f-I batch. usage: run_fi.sh "<S list>" "<cell list>" "<corner:temp list>" [nproc]
# Skips cases whose JSON exists. Output: sim/results/speed/fi_*.json + run_fi.log lines.
cd /work
NP=${4:-2}
for S in $1; do for c in $2; do for ct in $3; do
  co=${ct%%:*}; t=${ct##*:}
  [ -f sim/results/speed/fi_${c}_${co}_${t}_S${S}.json ] && continue
  python3 sim/tb/speed/tb_fi.py $c $co $t $S $NP 2>&1 | grep -v "^$" | tail -9 >> sim/results/speed/run_fi.log || echo "FAIL $c $co $t $S" >> sim/results/speed/run_fi.log
done; done; done
echo DONE
