#!/bin/bash
# re-run tt/27 and ss/0 at vreset 1.5 V, all modes (rev B step benches with the clamp-off DC nodeset)
cd /work
run() { rm -f sim/tb/e2/results/e2_$1_$2_1.50.json; python3 sim/tb/e2/tb_e2.py $1 $2 1.5 > sim/tb/e2/results/log_$1_$2_1.5.txt 2>&1; echo "$1 $2 rc=$?"; }
run typical 27 & run ss 0; wait
