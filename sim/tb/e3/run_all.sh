#!/bin/bash
# E3 full flow inside the EDA container, from /work (2 cores):  bash sim/tb/e3/run_all.sh
#   1 layout build (gen, magic DRC, KLayout DRC, LVS, PEX)          -> layout/e3/out/build_log.txt (+ the build's own logs)
#   2 schematic bench tt/27, ss/0, ff/85 (3 vbp_syn values each)    -> sim/tb/e3/results/log_sch_*.txt
#   3 PEX bench tt/27 (if extraction produced a netlist)             -> sim/tb/e3/results/log_pex_typical_27.txt
#   4 schematic MC, N = 100, tt/27, vbp_syn 2.58 V                   -> sim/tb/e3/results/log_mc.txt
#   then sim/tb/e3/results/summary.md
cd /work
R=sim/tb/e3/results; mkdir -p $R layout/e3/out
t0=$(date +%s)
st() { echo "[$(( $(date +%s) - t0 )) s] $*"; }
st "build"
bash layout/e3/build.sh > layout/e3/out/build_log.txt 2>&1; echo "build rc=$?" >> layout/e3/out/build_log.txt
cat layout/e3/out/build_log.txt
grep -E "routed|FAILED|e3_syn:" layout/e3/out/e3_syn_gen.log
run() { python3 sim/tb/e3/tb_e3.py $1 $2 $3 > $R/log_$1_$2_$3.txt 2>&1; st "$1 $2 $3 rc=$?"; }
run sch typical 27 & run sch ss 0; wait
run sch ff 85
if [ -s layout/e3/out/e3_syn_pex.spice ]; then run pex typical 27; else st "no PEX netlist: PEX bench skipped"; fi
python3 sim/tb/e3/tb_e3.py mc 100 1 2.58 > $R/log_mc.txt 2>&1; st "mc rc=$?"
python3 sim/tb/e3/tb_e3.py summary > $R/log_summary.txt 2>&1
cat $R/summary.md
st "done"
