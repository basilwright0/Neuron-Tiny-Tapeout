#!/bin/bash
# MIL-344 R2 (B1 re-pack, branch r2-b1-pack): one VM job = prep with the new bias_b1, legality check of the committed
# routes, reroute of the B1 analog outputs + every net the check flags, connectivity check, then the vm_top3 gate
# (assembly, extraction, LVS, magic + KLayout DRC/antenna, TT precheck; no PEX). Logs: layout/top/work/vmr2/.
# Usage (repo root, on the shared queue VM): bash layout/top/vm_r2.sh
cd "$(dirname "$0")/../.."
L=layout/top/work/vmr2; rm -rf $L; mkdir -p $L
step() { echo "$(date -u '+%F %T') $*" | tee -a $L/steps.log; }
step "start $(git log --oneline -1 2>/dev/null || echo no-git)"
bash scripts/eda.sh "cd layout/top && python3 ../../floorplan/floorplan.py > work/floorplan.log && python3 prep.py > work/prep.log && python3 route.py check" > $L/check_before.txt 2>&1
step "check rc=$? $(tail -1 $L/check_before.txt)"
ANA="vbp_syn el vbn_leak vbp_st vbn_prb vbn_ref aux3 vbn_ax vbp_w"
BAD=$(awk '/^BAD/{print $2}' $L/check_before.txt | tr '\n' ' ')
NETS=$(echo $ANA $BAD | tr ' ' '\n' | awk 'NF && !s[$0]++' | tr '\n' ' ')
step "reroute: $NETS"
bash scripts/eda.sh "cd layout/top && python3 -u route.py reroute $NETS" > $L/reroute.log 2>&1
step "reroute rc=$? $(grep -c ' OK' $L/reroute.log) OK, $(grep -c 'FAIL' $L/reroute.log) FAIL"
bash scripts/eda.sh "cd layout/top && python3 route.py check && python3 conncheck.py" > $L/check_after.txt 2>&1
step "check_after rc=$? $(grep '^check:' $L/check_after.txt)"
tail -5 $L/check_after.txt >> $L/steps.log
bash layout/top/vm_top3.sh nopex
cp -r layout/top/work/vm3 $L/
cp layout/top/work/routes.json $L/
step "end"
