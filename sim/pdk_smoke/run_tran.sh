#!/bin/bash
export PATH=/foss/tools/bin:$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD
cd /work/sim/pdk_smoke; python3 gen_tran.py
for f in out/tran_*.cir; do ngspice -b $f > ${f%.cir}.log 2>&1 || echo FAIL $f; done
python3 analyze_tran.py
