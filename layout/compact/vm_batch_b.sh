#!/bin/bash
# Boat VM batches for M2 layout B (user decision 2026-11-21 19:24 UTC: tall rows at the bottom, REF tall at (0,0),
# AH800 compact in a 37.44 um compact row with F2/F3/AH50). Usage: bash layout/compact/vm_batch_b.sh ah800|row3
#   ah800: compact AH800 (own cap row NX, CHAN 1.2 -> H 37.44): search + final       -> /home/user/ah800_{out.tgz,done}
#   row3:  tall REF (layout/slot, 45.74 um, 23 tracks) + F and AH50 at H 37.44 (CHAN 3.873), names cx*
#                                                                                    -> /home/user/row3_{out.tgz,done}
cd "$(dirname "$0")/../.."
IMG=hpretl/iic-osic-tools:2026.08
docker image inspect $IMG >/dev/null 2>&1 || docker pull $IMG > /dev/null 2>&1
case "$1" in
ah800)
  TAG=ah800 bash layout/compact/vm_compact.sh "slot_ah_800" "CHAN=1.2;CONG=0" 8 ;;
row3)
  E='export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod SLOT_H1=45.74 NTRACK=23 SKIPDEV=1; cd /work'
  docker run --rm -v "$PWD:/work" --entrypoint bash $IMG -c "$E && CELLS=slot_ref bash layout/slot/build.sh > layout/slot/out/tall_slot_ref.log 2>&1" &
  NAME_PREFIX=cx TAG=row3c bash layout/compact/vm_compact.sh "slot_ah_f slot_ah_50" "CHAN=3.873;CONG=0" 6
  wait
  tar czf /home/user/row3_out.tgz /home/user/row3c_out.tgz layout/slot/out/tall_slot_ref.log layout/slot/out/slot_ref* \
    layout/slot/slot_ref_* layout/slot/slot_ref.mag layout/slot/out/route_cache_slot_ref.json 2>/dev/null
  echo DONE > /home/user/row3_done ;;
esac
