#!/bin/bash
# Lint the control-plane RTL (run inside the EDA container from /work).
set -e
cd /work/rtl/revB
SRC="neuron_ctrl.v nc_spi.v nc_spk_chan.v nc_sync.v digital_lif.v"
W="-Wall -Wno-DECLFILENAME -Wno-MULTITOP -Wno-UNUSEDPARAM -Wno-LATCH"
verilator --lint-only $W --top-module neuron_ctrl -I. $SRC
verilator --lint-only $W --top-module neuron_ctrl -GLIF_W=8 -GCNT_W=12 -I. $SRC
iverilog -g2005 -Wall -I. -s neuron_ctrl -o /tmp/nc.vvp $SRC
echo LINT_OK
