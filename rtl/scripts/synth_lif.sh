#!/bin/bash
# Stand-alone area of digital_lif for W=8 and W=12.
set -e
cd /work/rtl; mkdir -p synth
LIB=synth/sc7t_tt_3v30.lib
cp /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib $LIB
for W in 8 12; do
yosys -q -p "read_liberty -lib $LIB; read_verilog -DNC_GF180_CELLS nc_sync.v digital_lif.v; chparam -set W $W digital_lif; synth -flatten -top digital_lif; dfflibmap -liberty $LIB; abc -liberty $LIB; opt_clean -purge; tee -o synth/area_lif_w$W.txt stat -liberty $LIB"
echo "W=$W: $(grep -E 'cells$' synth/area_lif_w$W.txt | head -1) $(grep 'Chip area' synth/area_lif_w$W.txt)"
done
rm -f $LIB
