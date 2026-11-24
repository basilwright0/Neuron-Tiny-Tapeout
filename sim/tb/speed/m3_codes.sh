#!/bin/bash
# MIL-309 item 3: per-chip vth_cmp code window for the CMP slot at S = 10000 (EL 1.5, FI_DEL 0.2, slot_cmp_h PEX).
#   vth_cmp at code c = the code-26 vdacr_vc PEX output of that corner (sim/results/vdac/gate: tt/27 1.57961,
#   ss/0 1.58145, ff/85 1.57512) + (c - 26) x 13.68 mV (topnet.vcodes M3 mapping). Codes 24, 25, 27, 28 (26 = vdac gate).
#   Plus code 26 with the high-speed leak-code calibration (info.md step 5.5: nominal x 13/12 at S = 10000,
#   FI_IBSCALE; the S = 100 reference stays uncalibrated, tag _cal13), all three corners.
#   Summary: python3 sim/tb/speed/vdac_gate_sum.py /work/sim/results/m3codes
cd /work
export FI_RESULTS=/work/sim/results/m3codes FI_DEL=0.2 FI_PEX=/work/layout/slot/out/slot_cmp_h_pex.spice
mkdir -p $FI_RESULTS
L=$FI_RESULTS/run.log
for ct in "typical 27 1.57961" "ss 0 1.58145" "ff 85 1.57512"; do
  set -- $ct
  for c in 24 25 27 28; do
    v=$(python3 -c "print(f'{$3 + ($c - 26) * 0.01368:.5f}')")
    for S in 100 10000; do
      FI_VTHC=$v python3 sim/tb/speed/tb_fi.py slot_cmp_h $1 $2 $S 1 >> $L 2>&1
    done
  done
  FI_VTHC=$3 FI_TAG=_cal13 python3 sim/tb/speed/tb_fi.py slot_cmp_h $1 $2 100 1 >> $L 2>&1
  FI_VTHC=$3 FI_TAG=_cal13 FI_IBSCALE=1.083333 python3 sim/tb/speed/tb_fi.py slot_cmp_h $1 $2 10000 1 >> $L 2>&1
done
python3 sim/tb/speed/vdac_gate_sum.py $FI_RESULTS >> $L 2>&1
echo CODES_DONE >> $L
