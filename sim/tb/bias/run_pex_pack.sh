#!/bin/bash
# MIL-133 B1-b: re-packed vdacr PEX DC check, tt/ss/ff x 0/27/85 -> out/pack/
cd /work/sim/tb/bias; mkdir -p out/pack${PACK_DIR}
J=${J:-2}
for c in tt ss ff; do for t in 0 27 85; do echo "$c $t"; done; done | xargs -P $J -L 1 bash -c '
  f=out/pack${PACK_DIR}/pack_$0_$1; python3 gen_pex_pack.py $f.cir --corner $0 --temp $1 && ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
echo DONE
