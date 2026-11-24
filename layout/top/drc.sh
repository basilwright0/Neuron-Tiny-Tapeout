#!/bin/bash
# Full-chip DRC of gds/<top>.gds (runs inside the EDA container, from layout/top):
#   KLayout gf180mcu deck exactly as the TT precheck runs it (variant gf180mcuD, all decks except density
#   and antenna; then the antenna deck), plus magic drc(full) on the assembled cell.
set -e
cd "$(dirname "$0")"
TOP=tt_um_basilwright0_analog_neurons
GDS=$PWD/../../gds/$TOP.gds
DECK=$PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc
for D in "main:all,-density,-antenna" "antenna:antenna"; do
    n=${D%%:*}; decks=${D#*:}
    klayout -b -r $DECK -rd input=$GDS -rd topcell=$TOP -rd report=$PWD/work/klayout_$n.lyrdb \
        -rd variant=gf180mcuD -rd run_mode=deep -rd decks=$decks -rd threads=${DRC_THREADS:-2} > work/klayout_$n.log 2>&1 || true
    python3 - work/klayout_$n.lyrdb $n <<'PY'
import sys, xml.etree.ElementTree as ET, collections
t = ET.parse(sys.argv[1]).getroot()
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT", sys.argv[2], sum(c.values()))
for k, v in c.most_common(25):
    print(f"  {v:6d}  {k}")
PY
done
cat > work/drc.tcl <<EOF
gds readonly true
gds read $GDS
load $TOP
select top cell
drc style drc(full)
drc check
drc catchup
set n [drc list count total]
puts "MAGIC_DRC_COUNT \$n"
set f [open work/magic_drc.txt w]
foreach {why boxes} [drc listall why] {
    puts \$f "[llength \$boxes]\t\$why"
    foreach b [lrange \$boxes 0 9] { puts \$f "\t[lmap v \$b {expr {\$v / 200.0}}]" }
}
close \$f
quit -noprompt
EOF
magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc work/drc.tcl > work/magic_drc.log 2>&1 || true
grep MAGIC_DRC_COUNT work/magic_drc.log || true
