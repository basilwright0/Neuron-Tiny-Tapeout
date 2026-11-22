#!/bin/bash
# MIL-133 vdac: schematic R_base sweep, tt/ss/ff x 0/27/85 -> out/vdac/
cd /work/sim/tb/bias; mkdir -p out/vdac
J=${J:-2}; BASES=${BASES:-53,58,59,60,61}
for c in tt ss ff; do for t in 0 27 85; do echo "$c $t"; done; done | xargs -P $J -L 1 bash -c '
  f=out/vdac/sw_$0_$1; python3 vdac_rbase_sweep.py $f.cir --corner $0 --temp $1 --bases '$BASES' && ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
echo DONE
