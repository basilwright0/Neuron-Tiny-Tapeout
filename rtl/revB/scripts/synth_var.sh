#!/bin/bash
# Area of neuron_ctrl for parameter variants: bash synth_var.sh "RB_REGS=0 CNT_W=12" ...
cd /work/rtl/revB; mkdir -p synth
LIB=synth/sc7t_tt_3v30.lib
cp /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib $LIB
for V in "$@"; do
  CH=""; for kv in $V; do CH="$CH chparam -set ${kv%%=*} ${kv##*=} neuron_ctrl;"; done
  yosys -q -p "read_liberty -lib $LIB; read_verilog -DNC_GF180_CELLS -I. nc_sync.v nc_spi.v nc_spk_chan.v digital_lif.v neuron_ctrl.v; $CH synth -flatten -top neuron_ctrl; dfflibmap -liberty $LIB; abc -liberty $LIB $ABC; opt_clean -purge; tee -q -o synth/var.txt stat -liberty $LIB" 
  echo "[$V] $(grep -E 'cells$' synth/var.txt | tail -1) $(grep 'Chip area' synth/var.txt | tail -1)"
done
rm -f $LIB
