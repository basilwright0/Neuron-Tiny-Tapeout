#!/bin/bash
# mismatch MC: 50 seeds, tt 27C, 2 idac_n + 2 idac_p per die, ranges 1 (10 nA), 3 (150 pA), 4 (10 pA)
cd /work/sim/tb/bias; mkdir -p out/mc
seq 1 50 | xargs -P 8 -I{} bash -c '
  f=out/mc/idac_mc_{}; python3 gen_idac.py $f.cir --seed {} --nidac 2 --ranges 1,3,4
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
python3 analyze_mc.py out/mc > out/idac_mc_summary.txt; cat out/idac_mc_summary.txt
