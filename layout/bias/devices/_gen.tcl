
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
set common {guard 0 topc 0 botc 0 m 1}
set rcommon {guard 0 m 1 nx 1}
mk p_w1_l1 pfet_03v3 [dict merge $common {w 1 l 1 nf 1}]
quit -noprompt
