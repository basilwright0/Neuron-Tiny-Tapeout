#!/bin/bash
# E1 (e1_fb, MIL-362): placement/route search on the VM (2 workers), then the best clean seed's final build (DRC, LVS,
# PEX). Run in the EDA container from the repo root:
#   bash layout/compact/vm_e1.sh "<variant>:<seed0>:<nseeds> ..." [STEPS]
#   variant A: two short n rows (EXTRA_N=1), CHANS 0.93,0.93,0.935,0.935;  B: one short n row, CHANS 1.45 x 4 (34.29)
cd "$(dirname "$0")"
mkdir -p out
export CELL=e1_fb MOM_STYLE=tall CB_W=4 STEPS=${2:-40000}
best=""
for spec in $1; do
  IFS=: read V S0 NS <<< "$spec"
  if [ "$V" = A ]; then export EXTRA_N=1 CHANS=0.93,0.93,0.935,0.935; else export EXTRA_N=0 CHANS=1.45,1.45,1.45,1.45; fi
  ON_BOAT=1 JOBS=2 NAME=s_ce1_fb_$V$S0 SEED0=$S0 SEEDS=$NS ITERS=40 python3 -u cgen.py searchonly > out/s_ce1_fb_$V$S0.log 2>&1
  grep -E "^seed" out/s_ce1_fb_$V$S0.log | head -4
  SEED=$(python3 -c "
import json; r=[x for x in json.load(open('out/s_ce1_fb_$V${S0}_search.json')) if not x['failed']]
print(r[0]['seed'] if r else '')")
  if [ -n "$SEED" ]; then best="$V $SEED"; break; fi
done
[ -z "$best" ] && { echo "NO CLEAN SEED"; exit 1; }
read V SEED <<< "$best"
if [ "$V" = A ]; then export EXTRA_N=1 CHANS=0.93,0.93,0.935,0.935; else export EXTRA_N=0 CHANS=1.45,1.45,1.45,1.45; fi
echo "best: variant $V seed $SEED"
SEED=$SEED FINAL_ITERS=60 CELLS=e1_fb bash build.sh final
