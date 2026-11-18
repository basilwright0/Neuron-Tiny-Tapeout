#!/bin/bash
# settling after a code change at the 150 pA point (range 3)
cd /work/sim/tb/bias; mkdir -p out/settle
{
for c in tt ss ff; do echo "python3 gen_settle.py out/settle/s_${c}_18_19.cir --corner $c --c0 18 --c1 19 && ngspice -b out/settle/s_${c}_18_19.cir > out/settle/s_${c}_18_19.log 2>&1"; done
echo "python3 gen_settle.py out/settle/s_tt_0_19.cir --c0 0 --c1 19 --tstop 12m && ngspice -b out/settle/s_tt_0_19.cir > out/settle/s_tt_0_19.log 2>&1"
echo "python3 gen_settle.py out/settle/s_tt_19_9.cir --c0 19 --c1 9 && ngspice -b out/settle/s_tt_19_9.cir > out/settle/s_tt_19_9.log 2>&1"
echo "python3 gen_settle.py out/settle/s_tt_held.cir --c0 18 --c1 19 --held --tstop 1m && ngspice -b out/settle/s_tt_held.cir > out/settle/s_tt_held.log 2>&1"
echo "python3 gen_settle.py out/settle/s_tt_200f.cir --c0 18 --c1 19 --cline 0.2p && ngspice -b out/settle/s_tt_200f.cir > out/settle/s_tt_200f.log 2>&1"
} | xargs -P 7 -I{} bash -c "{}"
