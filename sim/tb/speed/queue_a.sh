#!/bin/bash
# Speed track: f-I baselines (S = 100), S = 3000, and the raised-EL operating point. One ngspice at a time.
cd /work; O=sim/results/speed
bash sim/tb/speed/run_fi.sh '3000' 'slot_ah slot_cmp_h' 'typical:27 ss:0 ff:85 sf:0' 1
bash sim/tb/speed/run_fi.sh '100' 'slot_ah slot_cmp_h slot_ah_50 slot_ah_800' 'typical:27 ss:0' 1
for S in 3000 10000; do for ct in "ss 0" "sf 0" "typical 27"; do set -- $ct
  [ -f $O/fi_slot_ah_$1_$2_S${S}_EL1.50.json ] || FI_DEL=0.2 python3 sim/tb/speed/tb_fi.py slot_ah $1 $2 $S 1 2>&1 | tail -9 >> $O/run_fi.log
done; done
bash sim/tb/speed/run_fi.sh '2000' 'slot_cmp_h' 'typical:27 ss:0 ff:85' 1
for ct in "typical 27" "ss 0"; do set -- $ct
  [ -f $O/fi_slot_cmp_h_$1_$2_S10000_vthc1.5.json ] || FI_VTHC=1.5 python3 sim/tb/speed/tb_fi.py slot_cmp_h $1 $2 10000 1 2>&1 | tail -9 >> $O/run_fi.log
done
echo QADONE
