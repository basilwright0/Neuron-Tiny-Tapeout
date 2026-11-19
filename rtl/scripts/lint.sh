#!/bin/bash
# Lint the rev E control-plane RTL (run inside the EDA container from /work).
set -e
cd /work/rtl
SRC="neuron_ctrl.v nc_cfg.v nc_sync.v digital_lif.v"
W="-Wall -Wno-DECLFILENAME -Wno-MULTITOP -Wno-UNUSEDPARAM -Wno-LATCH"
verilator --lint-only $W --top-module neuron_ctrl -I. $SRC                         # default: TRIM_MASK C1FD
verilator --lint-only $W --top-module neuron_ctrl -GLIF_W=8 -GNTRIM=4 -I. $SRC
verilator --lint-only $W --top-module neuron_ctrl -GTRIM_MASK="16'hFFFF" -I. $SRC   # every nibble stored
iverilog -g2005 -Wall -I. -s neuron_ctrl -o /tmp/nc.vvp $SRC
iverilog -g2005 -Wall -I. -s neuron_ctrl -Pneuron_ctrl.LIF_W=8 -Pneuron_ctrl.NTRIM=4 -o /tmp/nc8.vvp $SRC
echo LINT_OK
