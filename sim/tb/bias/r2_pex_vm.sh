#!/bin/bash
# r2-b1-pack (MIL-344): PEX of the re-packed bias_b1 (no re-route: build.sh nogen), then the one-deck top-level PEX
# DC compare (b1int_pex3.py): schematic / base = fdcf2ad (shipped M3) PEX / new R2 PEX -> out/r2/pex3/summary.txt.
set -e
cd /work/layout/bias
PEX=1 CELLS=bias_b1 bash build.sh nogen 2>&1 | tee out/r2_pex_build.txt
cd /work/sim/tb/bias
mkdir -p out/r2/base out/r2/new out/r2/pex3
P=/work/layout/bias/out/bias_b1_pex.spice
cp $P out/r2/new_pex.spice
cp r2_base_pex.spice $P
python3 gen_pex_top.py out/r2/base/top.cir
cp out/r2/new_pex.spice $P
python3 gen_pex_top.py out/r2/new/top.cir
PEX3_D=out/r2 python3 b1int_pex3.py
ngspice -b out/r2/pex3/run.cir > out/r2/pex3/run.txt 2>&1
PEX3_D=out/r2 python3 b1int_pex3.py sum
