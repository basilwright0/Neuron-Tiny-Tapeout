#!/bin/bash
# Speed track: B1 rev C current DACs vs master current (S = 100 * I_nd / 1 uA).
# Reuses sim/tb/bias/gen_revc.py (read-only). -> sim/results/speed/bias/
G=/work/sim/tb/bias/gen_revc.py; O=/work/sim/results/speed/bias; mkdir -p $O
I0=1e-6,3e-6,1e-5,2e-5,3e-5,5e-5,1e-4
for ct in "tt 27" "ss 0" "ff 85" "sf 0" "fs 85" "ss 85" "ff 0"; do set -- $ct
  f=$O/idac_$1_$2_m0; python3 $G $f.cir idac --corner $1 --temp $2 --mode 0 --irefs $I0 --codes 0,1,8,16,31
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f
done
for ct in "tt 27" "ss 0" "ff 85"; do set -- $ct
  f=$O/idac_$1_$2_m1; python3 $G $f.cir idac --corner $1 --temp $2 --mode 1 --irefs 1.6e-5,1.6e-4,4.8e-4,1.6e-3 --codes 0,1,16,31
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f
done
echo DONE
