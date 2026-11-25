# e2_leak: draw (out/<cell>_paint.tcl from e2gen.py), DRC, GDS, LVS netlist, PEX netlist.
# Run from layout/e2/out:  NAME=e2_leak magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc ../build.tcl
set cell $::env(NAME)
source ${cell}_paint.tcl
load $cell
select top cell

drc style drc(full)
drc on
drc check
drc catchup
save $cell
set n [drc list count total]
puts "MAGIC_DRC_COUNT $n"
set f [open ${cell}_magic_drc.txt w]
puts $f "magic DRC, style drc(full), cell $cell: $n error tiles"
foreach {why boxes} [drc listall why] {
    puts $f "[llength $boxes]\t$why"
    foreach b $boxes { puts $f "\t[lmap v $b {expr {$v / 200.0}}]" }
}
close $f

gds write ${cell}.gds

file mkdir ext_$cell pex_$cell
extract path ext_$cell
extract all
ext2spice lvs
ext2spice -p ext_$cell -o ${cell}_ext.spice

extract path pex_$cell
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice -p pex_$cell -o ${cell}_pex.spice
quit -noprompt
