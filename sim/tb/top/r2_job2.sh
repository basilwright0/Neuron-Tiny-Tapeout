#!/bin/bash
# R2 PEX job 2 (MIL-362), in the EDA container: (1) the bay probe and the full-glue probe step, one at a time (both
# were OOM-killed (rc 137) when they ran next to each other in job 1); (2) vsrc coupling-C diagnostic: s10k and
# bias_spk off with TOP_VSRC_FIX=1 (topnet.vsrc_fix), in parallel. ngspice logs are kept in sim/results/top/*.log.
cd /work
L=sim/results/top/job2
mkdir -p $L
export TOP_THREADS=1
python3 - > $L/vsrc_fix_check.txt 2>&1 <<'P'
import os, sys
os.environ["TOP_VSRC_FIX"] = "1"
sys.path.insert(0, "sim/tb/top")
import topnet as T
T.build(T.config(), power="ideal")
r, a, m, g = T._cache["vsrc_fix"]
print(f"vsrc fix: removed {r * 1e15:.1f} fF vsrc-VGND, added {a * 1e15:.1f} fF (to nets {m * 1e15:.1f}, ground {g * 1e15:.1f})")
P
t0=$(date +%s)
timeout 40m python3 sim/tb/top/tb_top_bay.py probe typical 27 > $L/bay_probe.log 2>&1; echo "bay_probe rc=$? $(( ($(date +%s) - t0) / 60 )) min" >> $L/summary.txt
t0=$(date +%s)
( TOP_VSRC_FIX=1 timeout 70m python3 sim/tb/top/tb_top_s10k.py typical 27 > $L/s10k_vsrcfix.log 2>&1; echo "s10k_vsrcfix rc=$?" >> $L/summary.txt ) &
( TOP_VSRC_FIX=1 timeout 70m python3 sim/tb/top/tb_top_bias.py spk off > $L/spk_off_vsrcfix.log 2>&1; echo "spk_off_vsrcfix rc=$?" >> $L/summary.txt ) &
wait
echo "vsrcfix pair $(( ($(date +%s) - t0) / 60 )) min" >> $L/summary.txt
t0=$(date +%s)
TOP_GLUE=full timeout 40m python3 sim/tb/top/tb_top_probe.py step typical 27 > $L/probe_fullglue.log 2>&1; echo "probe_step_fullglue rc=$? $(( ($(date +%s) - t0) / 60 )) min" >> $L/summary.txt
free -g >> $L/summary.txt
