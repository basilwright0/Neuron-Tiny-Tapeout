#!/bin/bash
# E1 (e1_fb, MIL-362): placement/route search on the VM (2 workers), then the best seed's final build (DRC, LVS, PEX).
# Run in the EDA container from the repo root:  bash layout/compact/vm_e1.sh [SEEDS] [STEPS]
cd "$(dirname "$0")"
mkdir -p out
export CELL=e1_fb EXTRA_N=1 CHANS=0.93,0.93,0.935,0.935 MOM_STYLE=tall CB_W=4 STEPS=${2:-40000}
ON_BOAT=1 JOBS=2 NAME=s_ce1_fb SEEDS=${1:-8} ITERS=40 python3 -u cgen.py searchonly > out/s_ce1_fb.log 2>&1
SEED=$(python3 -c "
import json; r=[x for x in json.load(open('out/s_ce1_fb_search.json')) if not x['failed']]
print(r[0]['seed'] if r else '')")
grep -E "^seed" out/s_ce1_fb.log | head -8
[ -z "$SEED" ] && { echo "NO CLEAN SEED"; exit 1; }
echo "best seed $SEED"
SEED=$SEED FINAL_ITERS=60 CELLS=e1_fb bash build.sh final
