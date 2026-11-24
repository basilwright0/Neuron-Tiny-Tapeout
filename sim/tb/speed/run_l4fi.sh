#!/bin/bash
# Level 4 (docs/m2-level4-proposal.md): host-side batch of tb_fi.py runs on leak-OTA netlist variants.
# usage: sim/tb/speed/run_l4fi.sh <jobfile> [parallel=3]
#   jobfile lines: <variant> <cell> <corner> <temp> <S> [FI_DEL|-]
#   variant -> sim/results/level4/netlists/slot_<variant>.spice (copies of cells/neuron/slot.spice)
# Each job: millstone-heavy + nice 15 + scripts/eda.sh (2 ngspice each); output sim/results/level4/fi/.
cd "$(dirname "$0")/../../.."
P=${2:-3}
mkdir -p sim/results/level4/fi
grep -v '^#' "$1" | grep -v '^$' | xargs -P "$P" -L 1 bash -c '
v=$0; cell=$1; c=$2; t=$3; S=$4; dl=${5:-}
env="FI_RESULTS=/work/sim/results/level4/fi FI_SLOTLIB=/work/sim/results/level4/netlists/slot_$v.spice FI_TAG=_$v"
[ -n "$dl" ] && [ "$dl" != "-" ] && env="$env FI_DEL=$dl"
out=$(/home/basil/.local/bin/millstone-heavy --project "Tiny Tapeout" -- nice -n 15 scripts/eda.sh "$env python3 sim/tb/speed/tb_fi.py $cell $c $t $S 2" 2>&1 | grep -v "^$" | tail -9)
printf "%s\n" "== $v $cell $c $t $S del=${dl:-}" "$out" >> sim/results/level4/fi/run_fi.log
echo "done $v $cell $c $t $S $dl"'
