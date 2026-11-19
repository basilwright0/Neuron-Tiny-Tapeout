#!/bin/bash
# Full flow for the R1 corner block r1_corner (runs inside the EDA container):
#   scripts/eda.sh "bash layout/readout/build.sh"          # devices, generate, DRC, LVS, PEX
#   scripts/eda.sh "bash layout/readout/build.sh nogen"    # re-verify only (uses existing r1_corner_paint.tcl)
#   SKIPDEV=1 ... keeps devices/*.mag
# Also builds r1_ua1 (r1_corner + the ua[1] Metal3 strap through CH_BOT): magic + KLayout DRC.
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELL=r1_corner
mkdir -p out
if [ "$1" != "nogen" ] && [ -z "$SKIPDEV" ]; then
    (cd devices && magic -dnull -noconsole -rcfile $RC ../gen_devices.tcl > ../out/gen_devices.log 2>&1)
fi
if [ "$1" != "nogen" ]; then
    python3 r1gen.py
fi
export R1_CELL=$CELL
mkdir -p out/ext_$CELL out/pex_$CELL
magic -dnull -noconsole -rcfile $RC build.tcl > out/${CELL}_magic.log 2>&1
grep MAGIC_DRC_COUNT out/${CELL}_magic.log

netgen -batch lvs "out/${CELL}_ext.spice $CELL" "${CELL}_lvs.spice $CELL" \
    $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl out/${CELL}_lvs_report.txt > out/${CELL}_netgen.log 2>&1 || true
grep -E "Final result" out/${CELL}_lvs_report.txt | tail -1 || true

# KLayout gf180mcu DRC deck (variant D, flat; density excluded: it is a chip-level fill rule)
rm -f out/${CELL}_klayout_drc.lyrdb
klayout -b -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc \
    -rd input=$PWD/out/${CELL}.gds -rd topcell=$CELL -rd report=$PWD/out/${CELL}_klayout_drc.lyrdb \
    -rd variant=D -rd run_mode=flat -rd decks=all,-density > out/${CELL}_klayout_drc.log 2>&1 || true
klayout -b -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc     -rd input=$PWD/out/r1_ua1.gds -rd topcell=r1_ua1 -rd report=$PWD/out/r1_ua1_klayout_drc.lyrdb     -rd variant=D -rd run_mode=flat -rd decks=all,-density > out/r1_ua1_klayout_drc.log 2>&1 || true
for C in $CELL r1_ua1; do
python3 - out/${C}_klayout_drc.lyrdb $C <<'PY'
import sys, xml.etree.ElementTree as ET, collections
t = ET.parse(sys.argv[1]).getroot()
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT_DRC_COUNT", sys.argv[2], sum(c.values()))
for k, v in c.most_common():
    print(f"  {v:5d}  {k}")
PY
done
