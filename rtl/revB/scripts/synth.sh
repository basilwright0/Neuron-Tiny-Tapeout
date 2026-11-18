#!/bin/bash
set -e
cd /work/rtl/revB
mkdir -p synth
cp /foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib synth/sc7t_tt_3v30.lib
yosys -q -l synth/yosys.log scripts/synth.ys
rm -f synth/sc7t_tt_3v30.lib
