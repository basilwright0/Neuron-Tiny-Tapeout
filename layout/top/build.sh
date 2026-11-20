#!/bin/bash
# Top-level assembly of tt_um_basilwright0_analog_neurons (runs inside the EDA container):
#   scripts/eda.sh "nice -n 15 bash layout/top/build.sh"          # prep -> route -> assemble -> LVS
#   scripts/eda.sh "nice -n 15 bash layout/top/build.sh noroute"  # re-assemble from work/routes.json
#   scripts/eda.sh "nice -n 15 bash layout/top/build.sh drc"      # + magic DRC and KLayout DRC (slow)
# Outputs: mag/<top>.mag, gds/<top>.gds, lef/<top>.lef, layout/top/work/{routes.json,top_ext.spice,
#          top_ref.spice,lvs_report.txt,top_preview.png}
set -e
cd "$(dirname "$0")"
TOP=tt_um_basilwright0_analog_neurons
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
mkdir -p work
python3 ../../floorplan/floorplan.py > work/floorplan.log || { cat work/floorplan.log; exit 1; }
python3 prep.py > work/prep.log
if [ "$1" != "noroute" ]; then
    python3 -u route.py > work/route.log 2>&1
    grep -E "^FAIL|^done" work/route.log || true
fi
python3 plot.py > /dev/null
python3 assemble.py
python3 netlist.py
magic -dnull -noconsole -rcfile $RC work/assemble.tcl > work/assemble.log 2>&1
grep -iE "error|cannot|couldn't" work/assemble.log | grep -v "^Reading\|DRC" | head -20 || true
netgen -batch lvs "work/top_ext.spice $TOP" "work/top_ref.spice $TOP" \
    $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl work/lvs_report.txt > work/netgen.log 2>&1 || true
grep -E "Final result|Netlists do not match|Circuits match" work/lvs_report.txt | tail -3 || true
if [ "$1" == "drc" ] || [ "$2" == "drc" ]; then
    bash drc.sh
fi
