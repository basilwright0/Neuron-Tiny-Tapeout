#!/bin/bash
# MIL-133 M3 (top3): one VM job = full-chip build from the committed work/routes.json (assembly, extraction, LVS),
# magic DRC + KLayout DRC (precheck deck, antenna), TT precheck; if all pass, the full-chip PEX benches
# (sim/tb/top/vm_pex.sh, JOBS benches at once). Logs land in layout/top/work/vm3/ (inside the tree, for vmwait.sh).
# Usage (repo root, on the shared queue VM): bash layout/top/vm_top3.sh [nopex]
cd "$(dirname "$0")/../.."
L=layout/top/work/vm3; rm -rf $L; mkdir -p $L
step() { echo "$(date -u '+%F %T') $*" | tee -a $L/steps.log; }
step "start $(nproc) CPUs, $(free -g | awk '/Mem/{print $2}') GB, $(git log --oneline -1 2>/dev/null || echo no-git)"
bash scripts/eda.sh "DRC_THREADS=4 nice -n 5 bash layout/top/build.sh noroute drc" > $L/build.log 2>&1
LVS=$(grep -hE 'Final result|Circuits match|do not match' layout/top/work/lvs_report.txt | tail -1)
step "build rc=$? LVS: $LVS"
grep -hE '^KLAYOUT|MAGIC_DRC_COUNT' $L/build.log | tee -a $L/steps.log
bash scripts/eda.sh "bash scripts/precheck.sh" > $L/precheck.log 2>&1
step "precheck rc=$?"
tail -25 $L/precheck.log >> $L/steps.log
cp layout/top/work/lvs_report.txt layout/top/work/magic_drc.txt layout/top/work/klayout_*.lyrdb $L/ 2>/dev/null
ok=1
echo "$LVS" | grep -q "Circuits match uniquely" || ok=0
for k in "KLAYOUT main 0" "KLAYOUT antenna 0" "MAGIC_DRC_COUNT 0"; do grep -q "^$k\$" $L/build.log || ok=0; done
grep -qiE 'fail|error' <(tail -25 $L/precheck.log) && ok=0
step "gate ok=$ok"
if [ "$ok" = 1 ] && [ "$1" != nopex ]; then
    mkdir -p /home/user/top3_pex && rm -f /home/user/pex_ext.ok
    sed "s|^H=/home/user$|H=/home/user/top3_pex|" sim/tb/top/vm_pex.sh > sim/tb/top/vm_pex_top3.sh
    FORCE=1 JOBS=${JOBS:-3} bash sim/tb/top/vm_pex_top3.sh > $L/pex_vm.log 2>&1
    step "pex rc=$?"
    cp /home/user/top3_pex/pex_*.log $L/ 2>/dev/null
    cat /home/user/top3_pex/pex_steps.log >> $L/steps.log 2>/dev/null
fi
step "end"
