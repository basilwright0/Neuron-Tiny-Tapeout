# Build slot_ah in magic: draw (from slotgen.py output), DRC, GDS, LVS netlist, PEX netlist.
# Cell from env SLOT_CELL (slot_ah | slot_ah_p). Run from layout/slot:  SLOT_CELL=slot_ah magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc build.tcl
addpath devices
set cell $::env(SLOT_CELL)
source ${cell}_paint.tcl
load $cell
select top cell

# ---------------------------------------------------------------- DRC (full rule set)
drc style drc(full)
drc on
drc check
drc catchup
save $cell
set n [drc list count total]
puts "MAGIC_DRC_COUNT $n"
set f [open out/${cell}_magic_drc.txt w]
puts $f "magic DRC, style drc(full), cell $cell: $n error tiles"
foreach {why boxes} [drc listall why] {
    puts $f "[llength $boxes]\t$why"
    foreach b $boxes { puts $f "\t[lmap v $b {expr {$v / 200.0}}]" }
}
close $f

# ---------------------------------------------------------------- GDS
gds write out/${cell}.gds

# ---------------------------------------------------------------- LVS netlist (no parasitics)
extract path out/ext_$cell
extract all
ext2spice lvs
ext2spice -p out/ext_$cell -o out/${cell}_ext.spice

# ---------------------------------------------------------------- PEX netlist (all coupling caps)
extract path out/pex_$cell
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice -p out/pex_$cell -o out/${cell}_pex.spice
quit -noprompt
