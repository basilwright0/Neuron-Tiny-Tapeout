#!/bin/bash
# Boat VM (repo at /home/user/neuron, Docker EDA image, 4 vCPU / 8 GB): full-chip PEX spot checks on the M2 layout.
#   1. re-assemble the top from the committed layout/top/work/routes.json (build.sh noroute: gds/, work/ext, LVS)
#   2. full-chip flat R+C extraction (ext_rc.tcl -> work/pexr/top_rc_flat.spice) and C-only (ext_c.tcl -> work/pex)
#   3. node check (every neuron vm resolves in the flat netlist), then run_batch.sh pex: static coupling + kick
#      transient for every neuron, probe step, bias DC / spiking neighbours. No full-chip DC sweeps (M1: OOM).
#   4. packs /home/user/pex_out.tgz, writes /home/user/pex_done, self-stops if a VM id is given.
# Usage (repo root):  [JOBS=2] nohup bash sim/tb/top/vm_pex.sh [<VM id>] > /home/user/pex_vm.log 2>&1 &
# Logs: /home/user/pex_{build,ext_rc,ext_c,nodes,batch}.log; batch logs / summary in sim/results/top/batch/.
cd "$(dirname "$0")/../../.."
H=/home/user
rm -f $H/pex_done
JOBS=${JOBS:-2}                    # ~1-2 GB per full-chip ngspice job (vectors limited by topbench.deck `save`)
step() { echo "$(date -u '+%F %T') $*" >> $H/pex_steps.log; }
step "start, $(nproc) CPUs, $(free -g | awk '/Mem/{print $2}') GB, JOBS=$JOBS, $(git log --oneline -1)"

# Checkpoints: steps 1-2 leave $H/pex_ext.ok (the extracted netlists stay on the VM disk), and run_batch.sh leaves a
# .ok per finished bench, so a rerun after a VM stop or an OOM kill only repeats unfinished work (FORCE=1: redo all).
if [ -e $H/pex_ext.ok ] && [ "${FORCE:-0}" != 1 ] && [ -s layout/top/work/pexr/top_rc_flat.spice ]; then
  step "build + extraction done earlier ($(cat $H/pex_ext.ok)): skipped"
else
# 1. assembly + LVS from the committed routes
bash scripts/eda.sh "nice -n 15 bash layout/top/build.sh noroute" > $H/pex_build.log 2>&1
step "build noroute rc=$? : $(grep -hE 'Final result|Circuits match|do not match' layout/top/work/lvs_report.txt | tail -1)"

# 2. extractions (stale outputs removed first so a failed run cannot reuse them)
bash scripts/eda.sh "mkdir -p layout/top/work/pexr layout/top/work/pex && rm -f layout/top/work/pexr/top_rc_flat.spice \
  layout/top/work/pexr/top_flat*.ext layout/top/work/pex/top_c_flat.spice"      # in the container: files are root's
RC='$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc'   # expanded inside the container
bash scripts/eda.sh "cd layout/top/work/pexr && nice -n 15 magic -dnull -noconsole -rcfile $RC /work/sim/tb/top/ext_rc.tcl" \
  > $H/pex_ext_rc.log 2>&1
step "ext_rc rc=$? : $(ls -l layout/top/work/pexr/top_rc_flat.spice 2>&1)"
bash scripts/eda.sh "cd layout/top/work/ext && nice -n 15 magic -dnull -noconsole -rcfile $RC /work/sim/tb/top/ext_c.tcl" \
  > $H/pex_ext_c.log 2>&1
step "ext_c rc=$? : $(ls -l layout/top/work/pex/top_c_flat.spice 2>&1)"
grep -q "Circuits match uniquely" layout/top/work/lvs_report.txt && [ -s layout/top/work/pexr/top_rc_flat.spice ] \
  && [ -s layout/top/work/pex/top_c_flat.spice ] && date -u '+%F %T' > $H/pex_ext.ok
fi

# 3. node check, then the bench batch
if [ -s layout/top/work/pexr/top_rc_flat.spice ]; then
  bash scripts/eda.sh "python3 sim/tb/top/topnet.py --nodes" > $H/pex_nodes.log 2>&1
  step "node check rc=$? ($(grep -c MISSING $H/pex_nodes.log) missing)"
  if ! grep -qE "Circuits match uniquely" layout/top/work/lvs_report.txt || grep -q MISSING $H/pex_nodes.log; then
    step "LVS mismatch or missing victim nodes: benches skipped"   # don't spend hours on a broken netlist
  else
    B=sim/results/top/batch                      # jobs finished by a run without markers (summary line rc=0) count as done
    [ -f $B/summary_pex.txt ] && awk '$2=="rc=0"{print $1}' $B/summary_pex.txt | while read -r n; do
      [ -e $B/$n.ok ] || echo "from summary" > $B/$n.ok; done
    JOBS=$JOBS bash sim/tb/top/run_batch.sh pex > $H/pex_batch.log 2>&1
    step "batch rc=$? : $(tail -1 $H/pex_batch.log)"
  fi
else
  step "no top_rc_flat.spice: benches skipped"
fi

# 4. pack, mark done, self-stop
tar czf $H/pex_out.tgz $H/pex_*.log layout/top/work/lvs_report.txt layout/top/work/top_ext.spice \
  layout/top/work/pexr/top_rc_flat.spice layout/top/work/pexr/top_flat.res.ext \
  layout/top/work/pex/top_c_flat.spice sim/results/top/*.txt sim/results/top/*.json \
  sim/results/top/batch/*.log sim/results/top/batch/summary_*.txt 2>/dev/null
step "packed $(ls -l $H/pex_out.tgz 2>&1)"
echo DONE > $H/pex_done
[ -n "$1" ] && bash layout/compact/vm_selfstop.sh "$1" $H/pex_done 300
