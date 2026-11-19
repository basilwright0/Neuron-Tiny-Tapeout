#!/bin/bash
# B1 bias generator layout flow (runs inside the EDA container):
#   scripts/eda.sh "bash layout/bias/build.sh"                 # all cells: generate, DRC, LVS
#   CELLS="idac_p rx_n4" scripts/eda.sh "bash layout/bias/build.sh"
#   ... build.sh nogen   -> re-verify only (existing *_paint.tcl)
#   PEX=1 ...            -> also write the PEX netlist
set -e
cd "$(dirname "$0")"
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELLS=${CELLS:-"rx_n4 rx_n2 rx_n1 rx_p05 rx_p1 rx_p24 idac_n idac_p bias_rails bias_master bias_ladder bias_vi vdacr_el vdacr_vr vdacr_vc vdacr_vt"}
mkdir -p out
for CELL in $CELLS; do
    export BCELL=$CELL
    echo "=================== $CELL"
    if [ "$1" != "nogen" ]; then
        G=leafs.py; case $CELL in bias_vblk|bias_b1|bias_b1_*) G=topgen.py;; bias_vi|vdacr_*) G=leafs3.py;; bias_*|vref_*|vdac*) G=leafs2.py;; esac
        python3 -u $G $CELL > out/${CELL}_gen.log 2>&1 || { echo "GEN FAILED"; tail -5 out/${CELL}_gen.log; }
        grep -E "FAILED|reusing|AREA" out/${CELL}_gen.log || true
    fi
    mkdir -p out/ext_$CELL out/pex_$CELL
    magic -dnull -noconsole -rcfile $RC build.tcl > out/${CELL}_magic.log 2>&1
    grep MAGIC_DRC_COUNT out/${CELL}_magic.log || tail -5 out/${CELL}_magic.log
    REF=$(python3 refnet.py $CELL)
    netgen -batch lvs "out/${CELL}_ext.spice $CELL" "$REF $CELL" \
        $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl out/${CELL}_lvs_report.txt > out/${CELL}_netgen.log 2>&1 || true
    grep -E "Final result" out/${CELL}_lvs_report.txt | tail -1 || echo "LVS: no result"
    if [ -z "$NOKL" ]; then
    rm -f out/${CELL}_klayout_drc.lyrdb
    klayout -b -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc \
        -rd input=$PWD/out/${CELL}.gds -rd topcell=$CELL -rd report=$PWD/out/${CELL}_klayout_drc.lyrdb \
        -rd variant=D -rd run_mode=flat -rd decks=all,-density > out/${CELL}_klayout_drc.log 2>&1 || true
    python3 kl_count.py out/${CELL}_klayout_drc.lyrdb
    fi
done
