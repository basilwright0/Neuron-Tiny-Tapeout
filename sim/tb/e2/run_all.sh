#!/bin/bash
# E2 benches: tt/27, ss/0, ff/85 at vreset 1.0 and 1.5 V (chip vreset, docs/info.md), 2 in parallel.
# Run inside the EDA container from /work:  bash sim/tb/e2/run_all.sh [modes]
cd /work
mkdir -p sim/tb/e2/results
run() { python3 sim/tb/e2/tb_e2.py $1 $2 $3 $4 > sim/tb/e2/results/log_$1_$2_$3.txt 2>&1; echo "$1 $2 $3 rc=$?"; }
M=${1:-reset,droop,leak,probe}
for vr in 1.0 1.5; do
  run typical 27 $vr $M &
  run ss 0 $vr $M
  wait
  run ff 85 $vr $M
done
