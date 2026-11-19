#!/bin/bash
# Harden neuron_ctrl rev E with LibreLane.
# Usage (container): bash rtl/librelane/run.sh [config.json] [run-tag]
cd /work/rtl/librelane
CFG=${1:-config.json}
TAG=${2:+--run-tag $2 --overwrite}
librelane --pdk-root /foss/pdks --pdk gf180mcuD --scl gf180mcu_fd_sc_mcu7t5v0 --manual-pdk $TAG "$CFG" 2>&1 | tail -40
