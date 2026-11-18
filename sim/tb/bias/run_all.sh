#!/bin/bash
# B1 bias generator: regenerate cells and run every testbench (≈40 min on 18 cores)
cd /work && python3 cells/bias/gen_cells.py
cd /work/sim/tb/bias
bash run_idac_corners.sh > /dev/null
bash run_floor.sh
bash run_compliance.sh > /dev/null
bash run_idac_mc.sh > /dev/null
bash run_settle.sh > /dev/null
bash run_rest.sh > /dev/null
echo ALLDONE
