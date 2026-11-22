#!/bin/bash
# Boat VM (repo /home/user/neuron, 4 vCPU): level-3 CMP layout rebuild of slot_cmp_h (schematic 36be54a: det_cmp's
# vbp from a local vbn_prb leg, XNC nfet 1/2 + diode XPC pfet 1/2 -> vbp_cmp; pins unchanged).
#   Tall double frame 28 x 91.48 (SLOT_H1=45.74, NTRACK=23, as built on Nov 21). Placement in slotgen.py: XPC in
#   row B next to XPT (Xi1.XS moved to row A left), XNC right of the leak tail XMT under the vbn_prb column.
#   build.sh reuse: takes out/route_cache_slot_cmp_h.json if its key matches (routed locally, schedule 0, 11 iters),
#   else re-routes (~3-10 min) -> magic DRC -> GDS -> netgen LVS vs slot_cmp_h_lvs.spice (flatten.py, regenerated
#   by slotgen) -> KLayout DRC -> PEX + pex_summary; then the post-layout f-I (sim/tb/tb_slot_fi.py, sch vs pex)
#   at typical/27 C for S = 100 and S = 10000 (the level-3 target), in parallel.
# Packs /home/user/cmp_l3_out.tgz, touches /home/user/cmp_l3_done, then self-stops the VM if a VM id is given.
# Usage (repo root): bash layout/slot/vm_cmp_l3.sh [VM id]        [ROUTE=fresh: ignore the route cache]
cd "$(dirname "$0")/../.."
O=/home/user/cmp_l3
rm -f /home/user/cmp_l3_done /home/user/cmp_l3_out.tgz
mkdir -p $O layout/slot/out sim/results
S=$O/summary.txt
{ echo "rev $(git rev-parse --short HEAD) $(date -u)"; git status --short | head -20; } > $S
IMG=hpretl/iic-osic-tools:2026.08
docker image inspect $IMG >/dev/null 2>&1 || docker pull $IMG > $O/pull.log 2>&1
MODE=reuse; [ "$ROUTE" = "fresh" ] && MODE=

if ! grep -qE '^XPC +vbp_cmp +vbp_cmp +vdd +vdd +pfet_03v3' cells/neuron/slot.spice; then
  echo "ABORT: cells/neuron/slot.spice has no XPC vbp_cmp diode (need schematic commit 36be54a)" >> $S
else
  T0=$(date +%s)
  bash scripts/eda.sh "SLOT_H1=45.74 NTRACK=23 SKIPDEV=1 CELLS=slot_cmp_h nice -n 15 bash layout/slot/build.sh $MODE" \
    > $O/build.log 2>&1
  echo "build: $(( ($(date +%s) - T0) / 60 )) min" >> $S
  cat $O/build.log >> $S
  grep -E "^  (schedule|iter|UNROUTED)|reusing|FAILED" layout/slot/out/slot_cmp_h_route.log | tail -5 >> $S
  grep -E "XNC|XPC|XPT" layout/slot/slot_cmp_h_lvs.spice >> $S
  tail -1 layout/slot/slot_cmp_h_paint.tcl | grep -q "91.48um" || echo "WARNING: frame is not 28 x 91.48" >> $S
  if [ -s layout/slot/out/slot_cmp_h_pex.spice ]; then
    T0=$(date +%s)
    for SS in 100 10000; do
      bash scripts/eda.sh "nice -n 15 python3 sim/tb/tb_slot_fi.py typical 27 $SS slot_cmp_h" > $O/fi_S$SS.log 2>&1 &
    done
    wait
    echo "f-I: $(( ($(date +%s) - T0) / 60 )) min" >> $S
    for f in $O/fi_*.log; do echo "== $(basename $f)"; tail -n 8 $f; done >> $S
  else
    echo "no PEX netlist: f-I skipped" >> $S
  fi
fi

tar czf /home/user/cmp_l3_out.tgz $O layout/slot/out/slot_cmp_h* layout/slot/out/route_cache_slot_cmp_h.json \
  layout/slot/slot_cmp_h.mag layout/slot/slot_cmp_h_base.mag layout/slot/slot_cmp_h_paint.tcl \
  layout/slot/slot_cmp_h_lvs.spice layout/slot/preview_slot_cmp_h.png sim/results/slotfi_slot_cmp_h_* 2>/dev/null
touch /home/user/cmp_l3_done
[ -n "$1" ] && bash layout/compact/vm_selfstop.sh "$1" /home/user/cmp_l3_done 300
