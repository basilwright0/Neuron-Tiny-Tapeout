#!/bin/bash
# vdac (MIL-133): 10000x gate re-check at EL 1.5 (FI_DEL 0.2), post-layout cells, uncalibrated leak code.
#   CMP (slot_cmp_h PEX): vth_cmp = 1.58 V ideal (M2 reference run) and = the new vdacr_vc PEX output at the code
#   whose DC trip is closest to Vth 1.58 V (tt/27 code 26, ss/0 code 30, ff/85 code 30).
#   AH50 (czslot_ah_50 PEX): independent of vth_cmp, re-run for reference.   S = 100 and 10000 each.
cd /work
export FI_RESULTS=/work/sim/results/vdac/gate FI_DEL=0.2
mkdir -p $FI_RESULTS
L=$FI_RESULTS/run.log
JOBS=("typical 27 1.58" "typical 27 1.57961" "ss 0 1.58" "ss 0 1.6353" "ff 85 1.58" "ff 85 1.62625")
# GATE_SET=c26: ss/0 and ff/85 at their code-26 PEX outputs (tt/27 code 26 is in the default set)
[ "$GATE_SET" = c26 ] && JOBS=("ss 0 1.58145" "ff 85 1.57512")
for job in "${JOBS[@]}"; do
  set -- $job
  for S in 100 10000; do
    FI_PEX=/work/layout/slot/out/slot_cmp_h_pex.spice FI_VTHC=$3 python3 sim/tb/speed/tb_fi.py slot_cmp_h $1 $2 $S 2 >> $L 2>&1
  done
done
[ -n "$GATE_NOAH" ] || for ct in "ss 0" "typical 27" "ff 85"; do
  set -- $ct
  for S in 100 10000; do
    FI_PEX=/work/layout/compact/final/czslot_ah_50_pex.spice FI_TAG=_cz python3 sim/tb/speed/tb_fi.py slot_ah_50 $1 $2 $S 2 >> $L 2>&1
  done
done
echo GATE_DONE >> $L
