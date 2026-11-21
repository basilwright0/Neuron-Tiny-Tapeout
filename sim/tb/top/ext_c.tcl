# Full-chip C-only PEX of the assembled top (flat), from the .ext files that build.sh's assembly writes
# (layout/top/work/ext; magic extracts parasitic C by default, `ext2spice lvs` only hides it).
#   scripts/eda.sh "cd layout/top/work/ext && nice -n 15 magic -dnull -noconsole -rcfile \$PDK_ROOT/\$PDK/libs.tech/magic/\$PDK.magicrc /work/sim/tb/top/ext_c.tcl"
# Output: layout/top/work/pex/top_c_flat.spice (flat, all coupling caps >= 0 aF; node names are hierarchical paths)
drc off
ext2spice format ngspice
ext2spice hierarchy off
ext2spice scale off
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice subcircuit top on
ext2spice global off
ext2spice renumber off
ext2spice -p /work/layout/top/work/ext -o /work/layout/top/work/pex/top_c_flat.spice tt_um_basilwright0_analog_neurons
quit -noprompt
