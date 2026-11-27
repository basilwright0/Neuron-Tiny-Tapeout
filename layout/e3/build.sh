#!/bin/bash
# e3_syn flow (inside the EDA container, from the repo root):  bash layout/e3/build.sh [nogen]
#   generator (host or container python with klayout) -> magic: DRC, GDS, LVS netlist, PEX netlist -> netgen LVS
#   -> KLayout gf180mcu DRC (variant D, flat, no density).  Outputs in layout/e3/out.
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELL=e3_syn
mkdir -p out
[ "$1" = "nogen" ] || python3 e3gen.py out > out/${CELL}_gen.log 2>&1
cd out
rm -rf ext_$CELL pex_$CELL $CELL.mag
NAME=$CELL magic -dnull -noconsole -rcfile $RC ../build.tcl > ${CELL}_magic.log 2>&1
grep MAGIC_DRC_COUNT ${CELL}_magic.log || tail -20 ${CELL}_magic.log
netgen -batch lvs "${CELL}_ext.spice $CELL" "${CELL}_lvs.spice $CELL" \
    $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl ${CELL}_lvs_report.txt > ${CELL}_netgen.log 2>&1 || true
grep -E "Final result|match uniquely|do not match" ${CELL}_lvs_report.txt | tail -3 || true
rm -f ${CELL}_klayout_drc.lyrdb
klayout -b -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc \
    -rd input=$PWD/${CELL}.gds -rd topcell=$CELL -rd report=$PWD/${CELL}_klayout_drc.lyrdb \
    -rd variant=D -rd run_mode=flat -rd decks=all,-density > ${CELL}_klayout_drc.log 2>&1 || true
python3 - ${CELL}_klayout_drc.lyrdb <<'PY' | tee ${CELL}_klayout_drc_summary.txt
import sys, xml.etree.ElementTree as ET, collections
t = ET.parse(sys.argv[1]).getroot()
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT_DRC_COUNT", sum(c.values()))
for k, v in c.most_common():
    print(f"  {v:5d}  {k}")
PY
# deliverables (committed): layout/e3/final
mkdir -p ../final
cp $CELL.gds ${CELL}_lvs.spice ${CELL}_pex.spice ${CELL}_lvs_report.txt ${CELL}_magic_drc.txt ${CELL}_paint.tcl \
   ${CELL}_klayout_drc_summary.txt ${CELL}_pins.json ${CELL}_preview.png ../final/
cp ${CELL}_klayout_drc.log ../final/${CELL}_klayout_drc_log.txt
cp ${CELL}_netgen.log ../final/${CELL}_netgen_log.txt
grep -E "MAGIC_DRC_COUNT" ${CELL}_magic.log > ../final/${CELL}_magic_log.txt
