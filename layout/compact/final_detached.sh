#!/usr/bin/env bash
# Run one `build.sh final` in a detached Docker container (docker run -d): it survives the end of an agent turn,
# unlike scripts/eda.sh, whose client process is killed with the turn.
#   layout/compact/final_detached.sh <tag> VAR=value ...     e.g.  ... h_final CELLS=slot_ah_h SEED=0 SWEEP='CHAN=1.8'
# Log: layout/compact/out/<tag>.log; container name tt_<tag>. Check: docker ps -f name=tt_<tag>; tail out/<tag>.log
set -euo pipefail
cd "$(dirname "$0")/../.."
TAG="$1"; shift
IMAGE=hpretl/iic-osic-tools:2026.08
ENVS=""
for kv in "$@"; do ENVS="$ENVS export $(printf '%q' "$kv");"; done
CMD="export PATH=/foss/tools/bin:/foss/tools/klayout:\$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod; $ENVS cd /work/layout/compact && bash build.sh final > out/$TAG.log 2>&1"
docker run -d --rm --name "tt_$TAG" -v "$PWD:/work" --entrypoint bash "$IMAGE" -c "$CMD"
echo "launched container tt_$TAG, log layout/compact/out/$TAG.log"
