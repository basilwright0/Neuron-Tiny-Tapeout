#!/bin/bash
# MIL-319 smoke (in the EDA container, ~5 min): S = 10000 deck generation (node names, sources), DAC MC on 3 seeds,
# slot mismatch active (DC trip of slot_cmp_h differs between seeds).
cd /work
python3 - <<'PY'
import sys; sys.path.insert(0, "sim/tb/top")
import topbench as B, topnet as T
c = B.op_point(10000.0); c.update(T.vcodes(el=1.5, vreset=1.5, vth_cmp=1.58, vth_ref=0.6534)); c["i0"] = 11; c["r2"] = 27
print("sch_bias S10000", B.sch_bias(10000.0, codes=c, ib_x2=1))
PY
python3 sim/tb/top/tb_top_s10k.py typical 27 --deck || echo DECK_FAILED
D=/tmp/topdeck/s10k_typical_27.cir
wc -l $D; grep -n "^Icmp\|^Vm_r2_b0\|^Iax\|^Iref\|^Vvdd" $D | cut -c1-200; grep -c "^Is" $D; grep -n "^save" $D | cut -c1-300
FI_RESULTS=/work/sim/results/m3smoke python3 sim/tb/speed/mc_vdac_vc.py 3 tt
for s in 0 1 2; do
  FI_SEED=$s FI_GONLY=1 FI_RESULTS=/work/sim/results/m3smoke FI_DEL=0.2 FI_VTHC=1.59329 \
    FI_PEX=/work/layout/slot/out/slot_cmp_h_pex.spice python3 sim/tb/speed/tb_fi.py slot_cmp_h typical 27 10000 1
done
grep -h "mismatch\|seed" /work/sim/results/m3smoke/fidc_*mc1*.cir | head -3
echo SMOKE_DONE
