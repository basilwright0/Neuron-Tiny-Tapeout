#!/bin/bash
# vdac (MIL-133): CMP (slot_cmp_h PEX) DC trip at EL 1.5 for a list of vth_cmp levels, tt/27 ss/0 ff/85, S = 100 / 10000
cd /work
export FI_RESULTS=/work/sim/results/vdac FI_PEX=/work/layout/slot/out/slot_cmp_h_pex.spice FI_DEL=0.2 FI_GONLY=1
for ct in "typical 27" "ss 0" "ff 85"; do for S in 100 10000; do for v in ${VTHCS:-1.58 1.62}; do
  echo "$ct $S $v"; done; done; done | xargs -P 2 -L 1 bash -c 'FI_VTHC=$3 python3 sim/tb/speed/tb_fi.py slot_cmp_h $0 $1 $2 1 2>&1 | tail -1'
