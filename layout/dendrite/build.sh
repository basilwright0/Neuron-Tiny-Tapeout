#!/bin/bash
# Full flow for the D1 dendrite cell (runs inside the EDA container):
#   scripts/eda.sh "bash layout/dendrite/build.sh"          # devices, place/route, DRC, LVS, PEX
#   scripts/eda.sh "bash layout/dendrite/build.sh nogen"    # re-verify only (uses existing dend_d1_paint.tcl)
#   scripts/eda.sh "bash layout/dendrite/build.sh reuse"    # re-emit geometry from out/route_cache_dend_d1.json
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELL=dend_d1
mkdir -p out devices
if [ "$1" != "nogen" ]; then
    python3 dendgen.py devlist
    if [ -z "$SKIPDEV" ]; then
        (cd devices && magic -dnull -noconsole -rcfile $RC ../gen_devices.tcl > ../out/gen_devices.log 2>&1)
    fi
    python3 dendgen.py $1 > out/${CELL}_route.log 2>&1 || true
    grep -E "FAILED|reusing|placement issues" out/${CELL}_route.log
fi
mkdir -p out/ext_$CELL out/pex_$CELL
SLOT_CELL=$CELL magic -dnull -noconsole -rcfile $RC build.tcl > out/${CELL}_magic.log 2>&1
grep MAGIC_DRC_COUNT out/${CELL}_magic.log

# LVS (Cfb omitted from the reference: it is a MOM capacitor, value from PEX)
netgen -batch lvs "out/${CELL}_ext.spice $CELL" "${CELL}_lvs.spice $CELL" \
    $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl out/${CELL}_lvs_report.txt > out/${CELL}_netgen.log 2>&1 || true
grep -E "Final result" out/${CELL}_lvs_report.txt | tail -1 || true

# KLayout gf180mcu DRC deck (variant D, flat; density excluded: it is a chip-level fill rule)
rm -f out/${CELL}_klayout_drc.lyrdb
klayout -b -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc \
    -rd input=$PWD/out/${CELL}.gds -rd topcell=$CELL -rd report=$PWD/out/${CELL}_klayout_drc.lyrdb \
    -rd variant=D -rd run_mode=flat -rd decks=all,-density > out/${CELL}_klayout_drc.log 2>&1 || true
python3 - out/${CELL}_klayout_drc.lyrdb <<'PY'
import sys, xml.etree.ElementTree as ET, collections
t = ET.parse(sys.argv[1]).getroot()
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT_DRC_COUNT", sum(c.values()))
for k, v in c.most_common():
    print(f"  {v:5d}  {k}")
PY
python3 pex_summary.py out/${CELL}_pex.spice $CELL > out/${CELL}_pex_summary.txt || true
head -4 out/${CELL}_pex_summary.txt
