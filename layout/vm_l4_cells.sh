#!/bin/bash
# Boat VM (4 vCPU / 8 GB, repo /home/user/neuron, EDA via scripts/eda.sh): level-4 layout rebuild of every cell with
# the leak OTA (cells aabada4: leak_ota_deg/degx/dega and D1's ax_ota_h inputs XM1/XM2 and diodes XD1/XD2 L 1 -> 0.5 um,
# same W; docs/m2-level4-proposal.md section 5). AdEx is not here: it rides its own level-3 rebuild.
#
# Kept slot: the 0.5 um gates are drawn inside their old L = 1 um footprints (layout/slot/keptdev.py; KEPT_L in
# slotgen.py, dendgen.py, compact/cgen.py + geom.pitch), so the placements are unchanged and the routes replay:
#   tall H / CMP and D1 : build.sh reuse  -> the committed route caches match their keys (no routing; checked locally)
#   tall P              : derived from H's cache (P_FROM_H)
#   compact (5 cells)   : build.sh final with the level-3 SEED/SWEEP/CHANS/CB_W -> same placement, deterministic
#                         re-route on identical metal (local check: cslot_ah wl 2372.6, every metal shape identical)
# Per cell: generate, magic DRC, GDS, KLayout DRC (incl. antenna), netgen LVS, PEX, then the post-layout f-I
# (sim/tb/tb_slot_fi.py typical 27, S = 100 and 10000; compact via PEX_NAME) or, for D1, tb_synapse (pex + sch).
# A clean cell (magic 0, KLayout 0, LVS match, route complete) gets /home/user/l4/<cell>.ok, so a rerun skips it.
# Compact finals are copied to layout/compact/final only when clean; tall and D1 outputs are written in place
# (layout/slot, layout/slot/out, layout/dendrite, layout/dendrite/out: all tracked, compare with git diff).
# Order: tall H, P, CMP and D1 (cache replay, ~1-2 min each) first, then the 5 compact routes, 3 at a time, AH400 last.
# Packs /home/user/l4_out.tgz, touches /home/user/l4_done, then stops the VM 300 s later if a VM id is given.
# Usage (repo root): bash layout/vm_l4_cells.sh [VM id]          [ONLY="slot_ah_h czslot_ah_400": subset]
cd "$(dirname "$0")/.."
O=/home/user/l4
rm -f /home/user/l4_done /home/user/l4_out.tgz
mkdir -p $O layout/slot/out layout/dendrite/out layout/compact/out layout/compact/final sim/results
S=$O/summary.txt
{ echo "=== rev $(git rev-parse --short HEAD 2>/dev/null) $(date -u)"; git status --short 2>/dev/null | head -30; } >> $S
IMG=hpretl/iic-osic-tools:2026.08
docker image inspect $IMG >/dev/null 2>&1 || docker pull $IMG > $O/pull.log 2>&1
T00=$(date +%s)
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a $S; }
want() { [ -z "$ONLY" ] || [[ " $ONLY " == *" $1 "* ]]; }
done_ok() { [ -f $O/$1.ok ] && { log "$1: skipped (ok from an earlier run: $(head -1 $O/$1.ok))"; return 0; }; return 1; }
clean() {    # build log -> 0 if magic 0, KLayout 0, LVS match
  grep -q "^MAGIC_DRC_COUNT 0$" "$1" && grep -q "^KLAYOUT_DRC_COUNT 0$" "$1" && grep -q "Circuits match uniquely" "$1"
}
verdict() { grep -E "^MAGIC_DRC_COUNT|^KLAYOUT_DRC_COUNT|Final result|^ +[0-9]+ +[A-Z]" "$1" | tr '\n' ' '; }
fi_bench() { # <tag> <schematic cell> [PEX_NAME]: S = 100 and 10000 in parallel; same-cell runs serialised (shared files)
  local tag=$1 cell=$2 pn=$3 SS
  for SS in 100 10000; do
    ( flock 9
      bash scripts/eda.sh "${pn:+PEX_NAME=$pn }nice -n 15 python3 sim/tb/tb_slot_fi.py typical 27 $SS $cell" \
        > $O/fi_${tag}_S$SS.log 2>&1
      cp sim/results/slotfi_${cell}_typical_27_S$SS.json $O/fi_${tag}_S$SS.json 2>/dev/null
    ) 9> /tmp/l4fi_${cell}_S$SS.lock &
  done
  wait
  for SS in 100 10000; do
    echo "  f-I $tag S=$SS: $(grep -E '^ +[0-9.]+ ' $O/fi_${tag}_S$SS.log | awk '{print $4}' | tr '\n' ' ')(pex/sch)" >> $S
  done
}

# ------------------------------------------------------------------ guards: schematic and generators at level 4
ABORT=
grep -qE '^\.subckt leak_ota_degx .* li=0\.5u .* ld=0\.5u' cells/neuron/slot.spice || ABORT="slot.spice leak_ota_degx is not L 0.5"
grep -qE '^XM1 +a +in +s1 +vss +nfet_03v3 W=4u L=0\.5u' cells/dendrite/dendrite.spice || ABORT="$ABORT; ax_ota_h is not L 0.5"
grep -q '^KEPT_L' layout/slot/slotgen.py && grep -q '^KEPT_L' layout/dendrite/dendgen.py && grep -q '^KEPT_L' layout/compact/cgen.py \
  && [ -f layout/slot/keptdev.py ] || ABORT="$ABORT; generators without KEPT_L / keptdev.py (push the level-4 layout prep)"
if [ -n "$ABORT" ]; then
  log "ABORT: $ABORT"
else
# ------------------------------------------------------------------ tall cells (route cache replay)
for C in slot_ah_h slot_ah_p slot_cmp_h; do
  want $C || continue; done_ok $C && continue
  T0=$(date +%s)
  bash scripts/eda.sh "SLOT_H1=45.74 NTRACK=23 SKIPDEV=1 CELLS=$C nice -n 15 bash layout/slot/build.sh reuse" > $O/build_$C.log 2>&1
  R=$(grep -hE "reusing|derived from|^  iter|FAILED" layout/slot/out/${C}_route.log | tail -2 | tr '\n' ' ')
  log "$C: $(( $(date +%s) - T0 )) s  $(verdict $O/build_$C.log)  route: $R"
  grep -E "XXL_X(M|D)[12] " layout/slot/${C}_lvs.spice | head -2 | sed 's/^/  /' >> $S
  if clean $O/build_$C.log && grep -q "FAILED: none" layout/slot/out/${C}_route.log; then
    fi_bench $C $C
    echo "$(date -u +%H:%M) $(verdict $O/build_$C.log)" > $O/$C.ok
  else
    log "$C: NOT CLEAN (see $O/build_$C.log, layout/slot/out/${C}_route.log)"
  fi
done

# ------------------------------------------------------------------ D1 (route cache replay)
C=dend_d1
if want $C && ! done_ok $C; then
  T0=$(date +%s)
  bash scripts/eda.sh "ROUTE_HW=1.5 SKIPDEV=1 nice -n 15 bash layout/dendrite/build.sh reuse" > $O/build_$C.log 2>&1
  R=$(grep -hE "reusing|placement issues|FAILED" layout/dendrite/out/${C}_route.log | tr '\n' ' ')
  log "$C: $(( $(date +%s) - T0 )) s  $(verdict $O/build_$C.log)  route: $R"
  grep -cE "L=0\.5u" layout/dendrite/dend_d1_lvs.spice | sed 's/^/  devices at L 0.5 in the LVS reference: /' >> $S
  if clean $O/build_$C.log && grep -q "FAILED: none" layout/dendrite/out/${C}_route.log; then
    T0=$(date +%s)
    bash scripts/eda.sh "nice -n 15 python3 sim/tb/dendrite/tb_synapse.py typical 27 pex" > $O/bench_synapse_pex.log 2>&1 &
    bash scripts/eda.sh "nice -n 15 python3 sim/tb/dendrite/tb_synapse.py typical 27" > $O/bench_synapse_sch.log 2>&1 &
    wait
    log "$C benches: $(( $(date +%s) - T0 )) s"
    for f in pex sch; do echo "  == synapse $f"; grep -E "N=[2-4] " $O/bench_synapse_$f.log | head -6 | sed 's/^/  /'; done >> $S
    echo "$(date -u +%H:%M) $(verdict $O/build_$C.log)" > $O/$C.ok
  else
    log "$C: NOT CLEAN (see $O/build_$C.log)"
  fi
fi

# ------------------------------------------------------------------ compact cells (same seed, re-route), 3 at a time
# name | schematic cell | env (level-3 finals: vm_summary of compact_out / ah400e_cz; README, a72180d) | level-3 wl
compact() {
  local N=$1 C=$2 ENV=$3 WL=$4 T0=$(date +%s)
  bash scripts/eda.sh "cd layout/compact && NAME_PREFIX=${N%%slot*} CELLS=$C $ENV MOM_STYLE=tall STEPS=80000 FINAL_ITERS=60 nice -n 15 bash build.sh final" \
    > $O/build_$N.log 2>&1
  local F=$(grep -h "^FINAL" layout/compact/out/${N}_gen.log | tail -1)
  log "$N: $(( $(date +%s) - T0 )) s  $F (level 3: wl $WL)  $(verdict $O/build_$N.log)"
  if clean $O/build_$N.log && [[ "$F" == *"failed []"* ]]; then
    for x in .gds _lvs.spice _lvs_report.txt _magic_drc.txt _pex.spice; do cp layout/compact/out/$N$x layout/compact/final/; done
    cp layout/compact/out/${N}_paint.tcl layout/compact/out/${N}_place.json $O/ 2>/dev/null
    fi_bench $N $C $N
    cp $O/fi_${N}_S100.log layout/compact/final/fi_${N}.log
    cp $O/fi_${N}_S10000.log layout/compact/final/fi_${N}_S10000.log
    echo "$(date -u +%H:%M) $F $(verdict $O/build_$N.log)" > $O/$N.ok
  else
    log "$N: NOT CLEAN: needs a route search (local, parallel variants), see $O/build_$N.log"
  fi
}
JOBS=0
while read -r N C WL ENV; do
  [ -z "$N" ] && continue
  want $N || continue; done_ok $N && continue
  if [ $JOBS -ge 3 ]; then wait -n; JOBS=$((JOBS - 1)); fi
  compact $N $C "$ENV" $WL &
  JOBS=$((JOBS + 1))
  sleep 20
done <<'EOF'
cslot_ah      slot_ah     2372.6 CB_W=4  SEED=3 SWEEP='CHAN=1.2;CONG=0'
cslot_ah_f    slot_ah_f   2392.2 CB_W=4  SEED=4 SWEEP='CHAN=1.2;CONG=0'
czslot_ah_f   slot_ah_f   2471.1 CB_W=4  SEED=1 SWEEP='CHAN=2.825;CONG=0' CHANS=2.825,2.825,2.82
czslot_ah_50  slot_ah_50  2459.1 CB_W=4  SEED=0 SWEEP='CHAN=2.825;CONG=0' CHANS=2.825,2.825,2.82
czslot_ah_400 slot_ah_400 2592.9 CB_W=12 SEED=5 SWEEP='CHAN=1.8;CONG=0'
EOF
wait
fi

# ------------------------------------------------------------------ pack, done, self-stop
log "total $(( ($(date +%s) - T00) / 60 )) min; ok: $(cd $O && ls *.ok 2>/dev/null | sed 's/\.ok//' | tr '\n' ' ')"
TALL="slot_ah_h slot_ah_p slot_cmp_h"
tar czf /home/user/l4_out.tgz $O \
  $(for c in $TALL; do echo layout/slot/$c.mag layout/slot/${c}_base.mag layout/slot/${c}_paint.tcl layout/slot/${c}_lvs.spice \
      layout/slot/preview_$c.png layout/slot/out/$c.gds layout/slot/out/${c}_*.txt layout/slot/out/${c}_*.spice \
      layout/slot/out/${c}_*.log layout/slot/out/${c}_klayout_drc.lyrdb layout/slot/out/route_cache_$c.json; done) \
  layout/slot/devices/*_k*.mag layout/dendrite/devices/*_k*.mag \
  layout/dendrite/dend_d1.mag layout/dendrite/dend_d1_base.mag layout/dendrite/dend_d1_paint.tcl layout/dendrite/dend_d1_lvs.spice \
  layout/dendrite/preview.png layout/dendrite/out/dend_d1* layout/dendrite/out/route_cache_dend_d1.json \
  layout/compact/final layout/compact/out/c*slot_ah*_{gen,magic,netgen,klayout_drc}.log layout/compact/out/c*slot_ah*.png \
  sim/results/slotfi_* sim/results/dendrite/synapse_*typical_27.json 2>/dev/null
touch /home/user/l4_done
[ -n "$1" ] && bash layout/compact/vm_selfstop.sh "$1" /home/user/l4_done 300
