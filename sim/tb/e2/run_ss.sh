#!/bin/bash
# re-run the ss/0 corner only (DC gmin fallback), both vreset values in parallel
cd /work
for vr in ${VRS:-1.0 1.5}; do python3 sim/tb/e2/tb_e2.py ss 0 $vr > sim/tb/e2/results/log_ss_0_$vr.txt 2>&1 & done; wait
