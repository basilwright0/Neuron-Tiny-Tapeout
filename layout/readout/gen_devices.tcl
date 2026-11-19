# Phase 1: generate every transistor used in r1_corner (layout/readout) with the PDK's parametrized
# generators (gf180mcu::*_draw), one cell per unique size, saved into devices/.
# Run: scripts/eda.sh "cd layout/readout/devices && magic -dnull -noconsole -rcfile \$PDK_ROOT/\$PDK/libs.tech/magic/\$PDK.magicrc ../gen_devices.tcl"
proc mk {name type params} {
    load $name
    box values 0 0 0 0
    set p [dict merge [gf180mcu::${type}_defaults] $params]
    if {[catch {set p [gf180mcu::${type}_check $p]} err]} { puts "CHECK $name: $err" }
    gf180mcu::${type}_draw $p
    property library gf180mcu
    property gencell $type
    property parameters $p
    save $name
    puts "MADE $name"
}
# guard 0: no per-device ring (r1gen.py draws the rings); no gate contacts (r1gen.py draws one poly gate bar per device).
set common {guard 0 topc 0 botc 0 m 1}
source devlist.tcl
quit -noprompt
