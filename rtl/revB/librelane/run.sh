#!/bin/bash
# Harden neuron_ctrl with LibreLane. Usage (container): bash rtl/librelane/run.sh [config.json]
cd /work/rtl/revB/librelane
CFG=${1:-config.json}
librelane --pdk-root /foss/pdks --pdk gf180mcuD --scl gf180mcu_fd_sc_mcu7t5v0 --manual-pdk "$CFG" 2>&1 | tail -40
