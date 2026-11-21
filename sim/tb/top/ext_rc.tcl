# Full-chip flat R+C PEX (magic `extract do resistance` + `extresist all`) of the final GDS, flattened.
# extresist keeps R networks for VDPWR / VGND (every device terminal) and ~40 signal nets (vsrc, abus, el, vreset,
# stb, ...); every other net is one node with all its coupling C. (`extresist force`, `tolerance` and `threshold`
# do not change the selection in magic 8.3.681; a rm4 cut at the stripe ends to get PDN nodes breaks the power-net
# extraction, so the stripe-end PDN model of the IR-drop check uses sim/tb/top/pgrid.py instead.)
#   scripts/eda.sh "cd layout/top/work/pexr && nice -n 15 magic -dnull -noconsole -rcfile \$PDK_ROOT/\$PDK/libs.tech/magic/\$PDK.magicrc /work/sim/tb/top/ext_rc.tcl"
# Output: layout/top/work/pexr/top_rc_flat.spice
drc off
crashbackups stop
gds readonly true
gds read /work/gds/tt_um_basilwright0_analog_neurons.gds
load tt_um_basilwright0_analog_neurons
select top cell
flatten top_flat
load top_flat
puts "flattened:"
extract path /work/layout/top/work/pexr
extract do resistance
extract all
puts "extracted:"
extresist threshold 1000
extresist mindelay 0
extresist all
puts "extresist done:"
ext2spice format ngspice
ext2spice scale off
ext2spice extresist on
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice subcircuit top on
ext2spice -p /work/layout/top/work/pexr -o /work/layout/top/work/pexr/top_rc_flat.spice top_flat
puts "done:"
quit -noprompt
