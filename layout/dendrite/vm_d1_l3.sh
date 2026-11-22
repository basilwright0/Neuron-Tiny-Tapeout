#!/bin/bash
# Boat VM (repo /home/user/neuron, 4 vCPU): level-3 D1 layout update (schematic 387f708: pdet XNI 1/1 -> 1/0.5 in both
# subunits; XNH stays 1/1, same devices and pins, frame 70 x 104 unchanged).
#   full build: devlist + place/route (region 0 reused from the committed cache; regions 1/2 re-route: XNI's terminals
#   changed, it keeps its old 1 um slot via dendgen.SLOT_L so the rest of the row is unmoved) -> magic DRC -> GDS -> netgen LVS vs the regenerated
#   dend_d1_lvs.spice -> KLayout DRC -> PEX + pex_summary; then the post-layout plateau check
#   (tb_synapse.py typical 27 pex: clustered/distributed plateau threshold N, compare README: clustered N = 4)
#   with the schematic run of the same bench and tb_cnode pex alongside.
# Packs /home/user/d1_l3_out.tgz and writes /home/user/d1_l3_done. Does NOT stop the VM (another job may share it).
# Usage (repo root): bash layout/dendrite/vm_d1_l3.sh          [REUSE_REGIONS=0,1,2 to trust existing caches]
cd "$(dirname "$0")/../.."
O=/home/user/d1_l3
rm -f /home/user/d1_l3_done
mkdir -p $O layout/dendrite/out
S=$O/summary.txt
{ echo "rev $(git rev-parse --short HEAD) $(date -u)"; git status --short | head -20; } > $S
IMG=hpretl/iic-osic-tools:2026.08
docker image inspect $IMG >/dev/null 2>&1 || docker pull $IMG > $O/pull.log 2>&1

if ! grep -qE '^XNI .*nfet_03v3 W=1u L=0\.5u' cells/dendrite/dendrite.spice; then
  echo "ABORT: cells/dendrite/dendrite.spice has no XNI W=1u L=0.5u (need schematic commit 387f708)" >> $S
else
  T0=$(date +%s)
  bash scripts/eda.sh "REUSE_REGIONS=${REUSE_REGIONS:-} ROUTE_HW=1.5 SKIPDEV=1 nice -n 15 bash layout/dendrite/build.sh" \
    > $O/build.log 2>&1
  echo "build: $(( ($(date +%s) - T0) / 60 )) min" >> $S
  cat $O/build.log >> $S
  grep -E "XNI" layout/dendrite/dend_d1_lvs.spice >> $S
  if [ -s layout/dendrite/out/dend_d1_pex.spice ]; then
    T0=$(date +%s)
    bash scripts/eda.sh "nice -n 15 python3 sim/tb/dendrite/tb_synapse.py typical 27 pex" > $O/bench_synapse_pex.log 2>&1
    bash scripts/eda.sh "nice -n 15 python3 sim/tb/dendrite/tb_synapse.py typical 27" > $O/bench_synapse_sch.log 2>&1
    bash scripts/eda.sh "nice -n 15 python3 sim/tb/dendrite/tb_cnode.py pex" > $O/bench_cnode_pex.log 2>&1
    echo "benches: $(( ($(date +%s) - T0) / 60 )) min" >> $S
    for f in $O/bench_*.log; do echo "== $(basename $f)"; tail -n 12 $f; done >> $S
  else
    echo "no PEX netlist: benches skipped" >> $S
  fi
fi

D=layout/dendrite
tar czf /home/user/d1_l3_out.tgz $O \
  $D/dend_d1.mag $D/dend_d1_base.mag $D/dend_d1_paint.tcl $D/dend_d1_lvs.spice $D/preview.png $D/preview_place.png \
  $D/out/dend_d1.gds $D/out/dend_d1_ext.spice $D/out/dend_d1_pex.spice $D/out/dend_d1_pex_summary.txt \
  $D/out/dend_d1_lvs_report.txt $D/out/dend_d1_magic_drc.txt $D/out/dend_d1_klayout_drc.lyrdb $D/out/*.log \
  $D/out/route_cache_dend_d1.json $D/out/route_region*.json \
  sim/results/dendrite/synapse_pex_typical_27.json sim/results/dendrite/synapse_typical_27.json 2>/dev/null
echo DONE > /home/user/d1_l3_done
