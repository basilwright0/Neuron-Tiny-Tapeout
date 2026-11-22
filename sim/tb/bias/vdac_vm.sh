#!/bin/bash
# vdac (MIL-133): re-route bias_b1 with the R_base 60 vdacr_vc leaf, DRC/LVS/KLayout/PEX, frame check, then the
# one-deck top-level PEX DC compare (b1int_pex3.py): schematic / base = c2f370e (b1int) PEX / new PEX -> out/vdac/pex3.
set -e
cd /work/layout/bias
export PYTHONHASHSEED=0
PEX=1 CELLS=bias_b1 bash build.sh 2>&1 | tee out/vdac_build.txt
python3 chk_frame.py > out/vdac_chk_frame.txt 2>&1 || true
cd /work/sim/tb/bias
mkdir -p out/vdac/base out/vdac/new out/vdac/pex3
P=/work/layout/bias/out/bias_b1_pex.spice
cp $P out/vdac/new_pex.spice
cp b1int_base_pex.spice $P
python3 gen_pex_top.py out/vdac/base/top.cir
cp out/vdac/new_pex.spice $P
python3 gen_pex_top.py out/vdac/new/top.cir
PEX3_D=out/vdac python3 b1int_pex3.py
ngspice -b out/vdac/pex3/run.cir > out/vdac/pex3/run.txt 2>&1
PEX3_D=out/vdac python3 b1int_pex3.py sum
