#!/bin/bash
# Full flow for the neuron-array slot cells (runs inside the EDA container):
#   scripts/eda.sh "bash layout/slot/build.sh"            # both cells: devices, place/route, DRC, LVS, PEX
#   scripts/eda.sh "bash layout/slot/build.sh nogen"      # re-verify only (uses existing *_paint.tcl)
#   scripts/eda.sh "bash layout/slot/build.sh reuse"      # re-emit geometry from out/route_cache_<cell>.json
#   CELLS="slot_ah_p" ... to restrict the cell list; strip cells (trim_*) use elgen.py
# Cells: slot_ah (S), slot_ah_h (H: + gap trim), slot_ah_p (P: H with the leak tail gate on aux),
#        slot_ah_f (F: tail W/L halved), slot_cmp_h (CMP + gap trim, vth_cmp on aux), slot_ah_50, slot_ah_800,
#        slot_ref (REF follower on el), slot_dummy (S, no spk pin, taps tied off),
#        trim_tau4 (P-column leak-tau trim, TE strip). trim_el4 (unused) only on request.
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELLS=${CELLS:-"slot_ah slot_ah_h slot_ah_p slot_ah_f slot_cmp_h slot_ah_50 slot_ah_800 slot_ref slot_dummy trim_tau4"}
# P_AS_H=1: cut the P group -- P positions use slot_ah_h, no slot_ah_p, no trim_tau4 strip cells
if [ "$P_AS_H" = "1" ]; then CELLS=$(echo $CELLS | tr " " "\n" | grep -v -e "^slot_ah_p$" -e "^trim_tau4$" | tr "\n" " "); fi
mkdir -p out
if [ "$1" != "nogen" ] && [ -z "$SKIPDEV" ]; then
    python3 slotgen.py devlist
    (cd devices && magic -dnull -noconsole -rcfile $RC ../gen_devices.tcl > ../out/gen_devices.log 2>&1)
fi
for CELL in $CELLS; do
    export SLOT_CELL=$CELL
    echo "=================== $CELL"
    if [ "$1" != "nogen" ]; then
        GEN=slotgen.py; case $CELL in trim_*) GEN=elgen.py;; esac
        python3 $GEN $1 > out/${CELL}_route.log 2>&1 || true
        grep -E "FAILED|reusing" out/${CELL}_route.log
    fi
    mkdir -p out/ext_$CELL out/pex_$CELL
    magic -dnull -noconsole -rcfile $RC build.tcl > out/${CELL}_magic.log 2>&1
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
    python3 - out/${CELL}_klayout_drc.lyrdb <<'EOF'
import sys, xml.etree.ElementTree as ET, collections
t = ET.parse(sys.argv[1]).getroot()
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT_DRC_COUNT", sum(c.values()))
for k, v in c.most_common():
    print(f"  {v:5d}  {k}")
EOF
    if [ "${CELL#trim_}" = "$CELL" ]; then
        python3 pex_summary.py out/${CELL}_pex.spice $CELL > out/${CELL}_pex_summary.txt
        head -3 out/${CELL}_pex_summary.txt
    fi
done
