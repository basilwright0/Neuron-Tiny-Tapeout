#!/bin/bash
# Compact cells (runs inside the EDA container):
#   scripts/eda.sh "bash layout/compact/build.sh"              # generate (cgen.py search + route), DRC, LVS, PEX
#   scripts/eda.sh "bash layout/compact/build.sh nogen"        # re-verify the existing out/<name>_paint.tcl
#   scripts/eda.sh "bash layout/compact/build.sh noroute"      # placement only (DRC of devices + frame)
# env: CELLS (default slot_ah), SEEDS, STEPS, ITERS, JOBS, FINAL_ITERS (cgen.py search knobs)
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELLS=${CELLS:-"slot_ah"}
mkdir -p out
for CELL in $CELLS; do
    export CELL NAME=${NAME_PREFIX:-c}$CELL
    echo "=================== $CELL -> $NAME"
    if [ "$1" != "nogen" ]; then
        python3 -u cgen.py $1 > out/${NAME}_gen.log 2>&1 || true
        grep -E "FINAL|^seed|Error|error" out/${NAME}_gen.log | head -40 || true
    fi
    rm -f out/${NAME}.mag
    (cd out && magic -dnull -noconsole -rcfile $RC ../build.tcl > ${NAME}_magic.log 2>&1)
    grep MAGIC_DRC_COUNT out/${NAME}_magic.log
    netgen -batch lvs "out/${NAME}_ext.spice $NAME" "out/${NAME}_lvs.spice $NAME" \
        $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl out/${NAME}_lvs_report.txt > out/${NAME}_netgen.log 2>&1 || true
    grep -E "Final result" out/${NAME}_lvs_report.txt | tail -1 || true
    rm -f out/${NAME}_klayout_drc.lyrdb
    klayout -b -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc \
        -rd input=$PWD/out/${NAME}.gds -rd topcell=$NAME -rd report=$PWD/out/${NAME}_klayout_drc.lyrdb \
        -rd variant=D -rd run_mode=flat -rd decks=all,-density > out/${NAME}_klayout_drc.log 2>&1 || true
    python3 - out/${NAME}_klayout_drc.lyrdb <<'EOF'
import sys, xml.etree.ElementTree as ET, collections
t = ET.parse(sys.argv[1]).getroot()
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT_DRC_COUNT", sum(c.values()))
for k, v in c.most_common():
    print(f"  {v:5d}  {k}")
EOF
done
