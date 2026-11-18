#!/bin/bash
# Flattened area of neuron_ctrl for parameter variants: bash synth_var.sh "LIF_W=8 NTRIM=4" ...
cd /work/rtl; mkdir -p synth
LIB=synth/sc7t_tt_3v30.lib
cp /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib $LIB
for V in "$@"; do
  CH=""; for kv in $V; do CH="$CH chparam -set ${kv%%=*} ${kv##*=} neuron_ctrl;"; done
  T=synth/var_$(echo $V | tr ' =' '_-').txt
  yosys -q -p "read_liberty -lib $LIB; read_verilog -DNC_GF180_CELLS -I. nc_sync.v nc_cfg.v digital_lif.v neuron_ctrl.v; $CH synth -flatten -top neuron_ctrl; dfflibmap -liberty $LIB; abc -D 20000 -liberty $LIB; opt_clean -purge; tee -q -o $T stat -liberty $LIB"
  echo "[$V] $(grep -E 'cells$' $T | tail -1) $(grep 'Chip area' $T | tail -1)"
done
rm -f $LIB
