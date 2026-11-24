#!/bin/bash
# Boat VM batch (M2, 2026-11-21): REF compact at 29.42 um (CHAN 1.2) + post-layout f-I of the 29.42 um S/F/AH50.
# Packs /home/user/batch_out.tgz and writes /home/user/batch_done.
cd "$(dirname "$0")/../.."
IMG=hpretl/iic-osic-tools:2026.08
E='export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod; cd /work'
rm -f /home/user/batch_done layout/compact/out/vm_summary.txt
bash layout/compact/vm_compact.sh "slot_ref" "CHAN=1.2;CONG=0" 6 &
for p in "cslot_ah slot_ah" "cslot_ah_f slot_ah_f" "cslot_ah_50 slot_ah_50"; do
  set -- $p
  docker run --rm -v "$PWD:/work" --entrypoint bash $IMG -c "$E && PEX_NAME=$1 python3 sim/tb/tb_slot_fi.py typical 27 100 $2" > layout/compact/out/fi_$1.log 2>&1
done
wait
tar czf /home/user/batch_out.tgz layout/compact/out/fi_*.log layout/compact/out/cslot_ref* layout/compact/out/s_slot_ref.log \
  layout/compact/out/final_slot_ref.log layout/compact/out/vm_summary.txt 2>/dev/null
echo DONE > /home/user/batch_done
