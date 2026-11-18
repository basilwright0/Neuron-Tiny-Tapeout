#!/bin/bash
# Rev C synthesis: hierarchical breakdown (synth/area.txt) + parameter variants.
set -e
cd /work/rtl
mkdir -p synth
cp /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib synth/sc7t_tt_3v30.lib
yosys -q -l synth/yosys.log scripts/synth.ys
rm -f synth/sc7t_tt_3v30.lib
grep -E "Chip area" synth/area.txt
bash scripts/synth_var.sh "LIF_W=12 NTRIM=16" "LIF_W=8 NTRIM=16" "LIF_W=12 NTRIM=4" "LIF_W=8 NTRIM=4"
