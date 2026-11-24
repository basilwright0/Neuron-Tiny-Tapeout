#!/bin/bash
# Level 4: D1 before/after (leak OTAs at L 1 vs 0.5 um) at EL 1.3 / 1.5, trim code 3 (level-3 setting).
# usage: sim/tb/speed/run_l4d1.sh [parallel=3] [jobfile]; jobs = <before|after> <S> <DEL> (after = cells/ as edited)
cd "$(dirname "$0")/../../.."
H=/work/sim/results/level4/netlists/head
P=${1:-3}
{ if [ -n "${2:-}" ]; then cat "$2"; else printf "%s\n" "before 100 0" "before 10000 0" "after 100 0" "after 10000 0" "before 100 0.2" "before 10000 0.2" "after 100 0.2" "after 10000 0.2"; fi; } |
xargs -P "$P" -L 1 bash -c '
v=$0; S=$1; d=$2; H='"$H"'
env="D1_OUT=/work/sim/results/level4/d1_${v}_EL$d D1_TAG=_${v}_d$d D1_TRIM=3 D1_DEL=$d"
[ "$v" = before ] && env="$env D1_REPL=\"neuron/membrane.spice=$H/membrane.spice;dendrite/dtrim.spice=$H/dtrim.spice;dendrite/dendrite.spice=$H/dendrite.spice\""
out=$(/home/basil/.local/bin/millstone-heavy --project "Tiny Tapeout" -- nice -n 15 scripts/eda.sh "$env python3 sim/tb/speed/tb_d1.py $S typical:27,ss:0,ff:85 1" 2>&1 | grep -v "^$" | tail -4)
printf "%s\n" "== $v S=$S DEL=$d" "$out" >> sim/results/level4/d1_run.log
echo "done $v $S $d"'
