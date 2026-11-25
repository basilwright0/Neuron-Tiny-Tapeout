#!/bin/bash
# E2 benches: tt/27, ss/0, ff/85; vreset 1.5 V (chip value, docs/info.md) with the rev B vreset-step modes,
# 1.0 V without them. 2 in parallel. Run inside the EDA container from /work:  bash sim/tb/e2/run_all.sh
cd /work
mkdir -p sim/tb/e2/results
run() { python3 sim/tb/e2/tb_e2.py $1 $2 $3 $4 > sim/tb/e2/results/log_$1_$2_$3.txt 2>&1; echo "$1 $2 $3 rc=$?"; }
A=reset,droop,leak,probe,step; B=reset,droop,leak,probe
run typical 27 1.5 $A & run ss 0 1.5 $A; wait
run ff 85 1.5 $A & run typical 27 1.0 $B; wait
run ss 0 1.0 $B & run ff 85 1.0 $B; wait
