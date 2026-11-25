#!/bin/bash
# rev B vreset-step benches only (V1 = 1.5 V), 3 corners (2 in parallel)
cd /work
run() { python3 sim/tb/e2/tb_e2.py $1 $2 1.5 leak,step > sim/tb/e2/results/log_step_$1_$2.txt 2>&1; echo "$1 $2 rc=$?"; }
run typical 27 & run ss 0; wait
run ff 85
