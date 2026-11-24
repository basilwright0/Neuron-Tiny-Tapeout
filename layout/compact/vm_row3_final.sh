#!/bin/bash
# Boat VM: final builds of F and AH50 at H 37.44 (row 3 of layout B) for chosen seeds, per-channel heights CHANS.
# Usage: bash layout/compact/vm_row3_final.sh <F seed> <AH50 seed>   -> /home/user/row3f_{out.tgz,done}
cd "$(dirname "$0")"
IMG=hpretl/iic-osic-tools:2026.08
rm -f /home/user/row3f_done

for p in "slot_ah_f $1" "slot_ah_50 $2"; do
  set -- $p
  docker run --rm -v "$(cd ../.. && pwd):/work" --entrypoint bash $IMG -c "export PATH=/foss/tools/bin:/foss/tools/klayout:\$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod; cd /work/layout/compact && NAME_PREFIX=cx CELLS=$1 CHANS=3.87,3.875,3.875 MOM_STYLE=tall CB_W=4 STEPS=80000 SEED=$2 SWEEP='CHAN=3.875;CONG=0' FINAL_ITERS=60 bash build.sh final" > out/final_cx$1.log 2>&1 &

done
wait
tar czf /home/user/row3f_out.tgz out/cxslot_ah_f* out/cxslot_ah_50* out/final_cxslot_*.log 2>/dev/null
echo DONE > /home/user/row3f_done
