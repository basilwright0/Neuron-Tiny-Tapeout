#!/bin/bash
# Boat VM: search + final build of compact cells. Usage: bash layout/compact/vm_compact.sh "<cells>" "<SWEEP>" [SEEDS]
# Runs the search natively (python3, ON_BOAT=1, 4 workers), then the best seed's final build in the EDA container.
set -u
CELLS="$1"; SWEEP="$2"; SEEDS="${3:-6}"; NP="${NAME_PREFIX:-c}"; TAG="${TAG:-compact}"   # NP: layout name prefix
cd "$(dirname "$0")"
mkdir -p out          # git-ignored: absent in a fresh clone
IMG=hpretl/iic-osic-tools:2026.08
docker image inspect $IMG >/dev/null 2>&1 || docker pull $IMG > out/pull.log 2>&1
for C in $CELLS; do
  N=s_$NP$C
  ON_BOAT=1 JOBS=4 CELL=$C CB_W=4 MOM_STYLE=tall STEPS=80000 SWEEP="$SWEEP" SEEDS=$SEEDS ITERS=40 NAME=$N python3 -u cgen.py searchonly > out/$N.log 2>&1
  SEED=$(python3 -c "
import json; r=[x for x in json.load(open('out/${N}_search.json')) if not x['failed']]
print(r[0]['seed'] if r else '')")
  if [ -z "$SEED" ]; then echo "$C: no clean seed" >> out/vm_summary.txt; continue; fi
  docker run --rm -v "$(cd ../.. && pwd):/work" --entrypoint bash $IMG -c "export PATH=/foss/tools/bin:/foss/tools/klayout:\$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod; cd /work/layout/compact && NAME_PREFIX=$NP CELLS=$C MOM_STYLE=tall CB_W=4 STEPS=80000 SEED=$SEED SWEEP='$SWEEP' FINAL_ITERS=60 bash build.sh final" > out/final_$NP$C.log 2>&1
  echo "$NP$C seed $SEED: $(tr '\n' ' ' < out/final_$NP$C.log)" >> out/vm_summary.txt
done
tar czf /home/user/${TAG}_out.tgz out/c*_paint.tcl out/c*.gds out/c*_lvs.spice out/c*_pex.spice out/c*_lvs_report.txt out/c*_magic_drc.txt out/final_*.log out/s_*.log out/vm_summary.txt 2>/dev/null
echo DONE > /home/user/${TAG}_done
