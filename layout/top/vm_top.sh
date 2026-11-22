#!/bin/bash
# Boat VM: full top-level build (prep, route, assemble, LVS), DRC and TT precheck; packs /home/user/top_out.tgz,
# writes /home/user/top_done. Usage (repo root): [BUILD_MODE="noroute drc"] bash layout/top/vm_top.sh [<VM id> for the self-stop]
cd "$(dirname "$0")/../.."
rm -f /home/user/top_done
bash scripts/eda.sh "nice -n 15 bash layout/top/build.sh ${BUILD_MODE:-drc}"   # BUILD_MODE="noroute drc": re-assemble from work/routes.json > /home/user/top_build.log 2>&1
bash scripts/eda.sh "bash scripts/precheck.sh" > /home/user/top_precheck.log 2>&1
tar czf /home/user/top_out.tgz /home/user/top_build.log /home/user/top_precheck.log layout/top/work/*.log \
  layout/top/work/routes.json layout/top/work/lvs_report.txt layout/top/work/top_preview.png layout/top/work/magic_drc.txt \
  layout/top/work/*.lyrdb mag/tt_um_basilwright0_analog_neurons.mag gds/tt_um_basilwright0_analog_neurons.gds \
  lef/tt_um_basilwright0_analog_neurons.lef 2>/dev/null
echo DONE > /home/user/top_done
[ -n "$1" ] && bash layout/compact/vm_selfstop.sh "$1" /home/user/top_done 300
