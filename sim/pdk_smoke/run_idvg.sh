#!/bin/bash
export PATH=/foss/tools/bin:$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD
cd /work/sim/pdk_smoke
for c in typical ff ss; do for t in 27 85; do
  sed -e "s/@CORNER@/$c/g" -e "s/@TEMP@/$t/g" idvg.cir.tmpl > out/idvg_${c}_${t}.cir
  ngspice -b out/idvg_${c}_${t}.cir > out/idvg_${c}_${t}.log 2>&1 || echo "FAIL $c $t"
done; done
python3 analyze_idvg.py
