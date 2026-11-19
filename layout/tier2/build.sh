#!/bin/bash
# Full flow for the Tier-2 cells (runs inside the EDA container):
#   scripts/eda.sh "bash layout/tier2/build.sh"            # devices, place/route, DRC, LVS, PEX (all cells)
#   scripts/eda.sh "CELLS=adex_a1 bash layout/tier2/build.sh"
#   scripts/eda.sh "bash layout/tier2/build.sh nogen"      # re-verify only (existing <cell>_paint.tcl)
#   scripts/eda.sh "bash layout/tier2/build.sh reuse"      # re-emit geometry from out/route_cache_<cell>.json
# SKIPDEV=1 keeps devices/*.mag. scdend_s1w = the 72 x 40 layout variant of scdend_s1 (same netlist).
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELLS=${CELLS:-"adex_a1 scdend_s1 scdend_s1w"}
mkdir -p out devices
if [ "$1" != "nogen" ] && [ -z "$SKIPDEV" ]; then
    python3 t2gen.py devlist
    (cd devices && magic -dnull -noconsole -rcfile $RC ../gen_devices.tcl > ../out/gen_devices.log 2>&1)
fi
for CELL in $CELLS; do
    echo "=== $CELL"
    if [ "$1" != "nogen" ]; then
        python3 t2gen.py $CELL $1 > out/${CELL}_route.log 2>&1 || true
        grep -E "FAILED|reusing|placement issues" out/${CELL}_route.log
    fi
    mkdir -p out/ext_$CELL out/pex_$CELL
    SLOT_CELL=$CELL magic -dnull -noconsole -rcfile $RC build.tcl > out/${CELL}_magic.log 2>&1
    grep MAGIC_DRC_COUNT out/${CELL}_magic.log

    # LVS (MOM capacitors omitted from the reference: values from PEX)
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
    case $CELL in
        adex_a1)   NODES=vm,vw,spk,vr; PAIRS=spk-vm ;;
        scdend_s1*) NODES=vs,d,ca,cl,spk; PAIRS=spk-vs,ca-vss,cl-vss,ca-d,ca-vs ;;
    esac
    python3 pex_summary.py out/${CELL}_pex.spice $CELL $NODES $PAIRS > out/${CELL}_pex_summary.txt || true
    cat out/${CELL}_pex_summary.txt
done
