#!/bin/bash
# Level-3 CMP (docs/m2-level3-proposal.md 2.1): host-side batch of tb_fi.py runs on netlist copies.
# usage: sim/tb/speed/run_l3cmp.sh <jobfile> [parallel=4]
#   jobfile lines: <variant> <corner> <temp> <S> [FI_VTHC|-] [FI_DEL|-] [FI_IPRB]
#   variant = before | i05 | i1 | i2 -> sim/results/level3_cmp/netlists/slot_<variant>.spice
# Each job: millstone-heavy + nice 15 + scripts/eda.sh; output sim/results/level3_cmp/fi/, log run_fi.log there.
cd "$(dirname "$0")/../../.."
P=${2:-4}
mkdir -p sim/results/level3_cmp/fi
grep -v '^#' "$1" | grep -v '^$' | xargs -P "$P" -L 1 bash -c '
v=$0; c=$1; t=$2; S=$3; vc=${4:-}; dl=${5:-}; ip=${6:-}
env="FI_RESULTS=/work/sim/results/level3_cmp/fi FI_SLOTLIB=/work/sim/results/level3_cmp/netlists/slot_$v.spice FI_TAG=_$v"
[ -n "$vc" ] && [ "$vc" != "-" ] && env="$env FI_VTHC=$vc"
[ -n "$dl" ] && [ "$dl" != "-" ] && env="$env FI_DEL=$dl"
[ -n "$ip" ] && env="$env FI_IPRB=$ip"
out=$(/home/basil/.local/bin/millstone-heavy --project "Tiny Tapeout" -- nice -n 15 scripts/eda.sh "$env python3 sim/tb/speed/tb_fi.py slot_cmp_h $c $t $S 2" 2>&1 | grep -v "^$" | tail -9)
printf "%s\n" "== $v $c $t $S vthc=${vc:-} del=${dl:-} iprb=${ip:-}" "$out" >> sim/results/level3_cmp/fi/run_fi.log
echo "done $v $c $t $S $vc $dl"'
