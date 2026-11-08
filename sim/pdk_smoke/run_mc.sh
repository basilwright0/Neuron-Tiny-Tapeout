#!/bin/bash
export PATH=/foss/tools/bin:$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD
cd /work/sim/pdk_smoke; rm -f out/mc_*
# 1) mismatch only, 30 instances/geometry, two seeds
for s in 1 2; do python3 gen_mc.py 30 $s typical 0 1; done
# 2) control: mismatch off (all instances identical)
python3 gen_mc.py 30 1 typical 0 0
# 3) global + mismatch via 'statistical' lib (one die per seed)
for s in 11 12 13 14 15; do python3 gen_mc.py 30 $s statistical 1 1; done
for f in out/mc_*.cir; do ngspice -b $f > ${f%.cir}.log 2>&1 || echo FAIL $f; done
python3 analyze_mc.py
